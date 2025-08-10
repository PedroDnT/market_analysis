#!/usr/bin/env python3
"""
Position Risk Manager
--------------------
Combines position fetching with volatility analysis to provide 
systematic risk management recommendations for all open positions.

This script:
1. Fetches current open positions from Bybit
2. Analyzes volatility for each position's symbol
3. Calculates optimal SL/TP levels based on volatility and leverage
4. Generates comprehensive risk management report
"""

import os
import json
import math
import datetime as dt
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

# Import position fetching functionality
from get_position import fetch_bybit_positions

# Import volatility analysis functions
from garch_vol_triggers import (
    get_klines_bybit,
    get_live_price_bybit,
    get_bybit_market_info,
    compute_atr,
    sigma_ann_and_sigma_H_from_har,
    garch_sigma_ann_and_sigma_H,
    sl_tp_and_size
)

class PositionRiskManager:
    """Manages risk analysis for all open positions."""
    
    def __init__(self, sandbox: bool = False):
        """Initialize the risk manager.
        
        Args:
            sandbox: If True, use Bybit testnet
        """
        self.sandbox = sandbox
        self.positions = []
        self.risk_analysis = {}
        
    def fetch_positions(self) -> List[Dict[str, Any]]:
        """Fetch current open positions."""
        print("=" * 80)
        print("Fetching current open positions...")
        print("=" * 80)
        
        self.positions = fetch_bybit_positions()
        
        if not self.positions:
            print("No open positions found.")
            return []
            
        print(f"Found {len(self.positions)} open position(s)")
        return self.positions
    
    def analyze_position_volatility(self, position: Dict[str, Any], 
                                   timeframe: str = "1h", 
                                   lookback_days: int = 30) -> Dict[str, Any]:
        """Analyze volatility for a single position.
        
        Args:
            position: Position data dictionary
            timeframe: Timeframe for volatility analysis
            lookback_days: Days of historical data to analyze
            
        Returns:
            Dictionary with volatility metrics and recommended SL/TP levels
        """
        symbol = position['symbol']
        side = position['side'].lower()
        entry_price = position['entryPrice']
        leverage = position.get('leverage', 10.0)
        
        print(f"\nAnalyzing {symbol}...")
        
        # Get market info for tick size
        market_info = get_bybit_market_info(symbol, sandbox=self.sandbox)
        tick_size = market_info['tick_size'] if market_info else 0.00001
        
        # Fetch historical data
        try:
            df = get_klines_bybit(
                symbol=symbol,
                timeframe=timeframe,
                since=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=lookback_days),
                sandbox=self.sandbox
            )
            
            if df.empty:
                print(f"  Warning: No historical data for {symbol}")
                return self._get_default_risk_params(position)
                
        except Exception as e:
            print(f"  Error fetching data for {symbol}: {e}")
            return self._get_default_risk_params(position)
        
        # Calculate ATR
        df["ATR20"] = compute_atr(df, period=20)
        atr = float(df["ATR20"].iloc[-1])
        atr_pct = (atr / entry_price) * 100
        
        # Get current live price
        live_price = get_live_price_bybit(symbol, sandbox=self.sandbox)
        if live_price is None:
            live_price = float(df["close"].iloc[-1])
        
        # Calculate volatility using multiple methods
        volatility_metrics = {}
        
        # HAR-RV volatility
        try:
            H_hours = 4  # 4-hour horizon for SL/TP
            sigma_ann_har, sigma_H_har = sigma_ann_and_sigma_H_from_har(
                df["close"], interval=timeframe, horizon_hours=H_hours
            )
            volatility_metrics['har_sigma_ann'] = sigma_ann_har
            volatility_metrics['har_sigma_H'] = sigma_H_har
        except Exception as e:
            print(f"  HAR-RV failed: {e}")
            volatility_metrics['har_sigma_ann'] = None
            volatility_metrics['har_sigma_H'] = None
        
        # GARCH volatility
        try:
            sigma_ann_garch, sigma_H_garch, _ = garch_sigma_ann_and_sigma_H(
                df["close"], interval=timeframe, horizon_hours=H_hours
            )
            volatility_metrics['garch_sigma_ann'] = sigma_ann_garch
            volatility_metrics['garch_sigma_H'] = sigma_H_garch
        except Exception as e:
            print(f"  GARCH failed: {e}")
            volatility_metrics['garch_sigma_ann'] = None
            volatility_metrics['garch_sigma_H'] = None
        
        # Determine which volatility measure to use
        if volatility_metrics['har_sigma_H']:
            primary_sigma = volatility_metrics['har_sigma_H']
            vol_method = "HAR-RV"
        elif volatility_metrics['garch_sigma_H']:
            primary_sigma = volatility_metrics['garch_sigma_H']
            vol_method = "GARCH"
        else:
            # Fallback to ATR-based volatility
            primary_sigma = atr / entry_price
            vol_method = "ATR"
        
        # Adjust risk parameters based on leverage
        # Higher leverage = tighter stops
        if leverage >= 20:
            k_sl = 0.8  # Very tight stop for high leverage
            m_tp = 1.8  # Conservative target
        elif leverage >= 15:
            k_sl = 1.0
            m_tp = 2.0
        elif leverage >= 10:
            k_sl = 1.2
            m_tp = 2.2
        else:
            k_sl = 1.5
            m_tp = 2.5
        
        # Calculate SL/TP levels with optimal position sizing
        target_risk_dollars = position['notional'] * 0.02  # Risk 2% of position notional
        risk_params = sl_tp_and_size(
            entry_price=entry_price,
            sigma_H=primary_sigma,
            k=k_sl,
            m=m_tp,
            side=side,
            R=target_risk_dollars,
            tick_size=tick_size
        )
        
        # Check liquidation buffer if liquidation price exists
        liquidation_price = position.get('liquidationPrice')
        liq_buffer_safe = True
        liq_buffer_ratio = None
        
        if liquidation_price:
            if side == 'long':
                sl_to_liq_distance = abs(risk_params['SL'] - liquidation_price)
                sl_to_entry_distance = abs(entry_price - risk_params['SL'])
                if sl_to_entry_distance > 0:
                    liq_buffer_ratio = sl_to_liq_distance / sl_to_entry_distance
                    liq_buffer_safe = risk_params['SL'] > liquidation_price * 1.1  # 10% buffer
            else:  # short
                sl_to_liq_distance = abs(liquidation_price - risk_params['SL'])
                sl_to_entry_distance = abs(risk_params['SL'] - entry_price)
                if sl_to_entry_distance > 0:
                    liq_buffer_ratio = sl_to_liq_distance / sl_to_entry_distance
                    liq_buffer_safe = risk_params['SL'] < liquidation_price * 0.9
        
        # Calculate dollar risk and reward using OPTIMAL position size
        optimal_position_size = risk_params['Q']  # This is the size that gives us target_risk_dollars
        current_position_size = position['size']
        
        # Calculate risk/reward for the OPTIMAL position size (what we should have)
        if side == 'long':
            optimal_dollar_risk = optimal_position_size * (entry_price - risk_params['SL'])
            optimal_dollar_reward = optimal_position_size * (risk_params['TP'] - entry_price)
            sl_pct = ((risk_params['SL'] - entry_price) / entry_price) * 100
            tp_pct = ((risk_params['TP'] - entry_price) / entry_price) * 100
        else:
            optimal_dollar_risk = optimal_position_size * (risk_params['SL'] - entry_price)
            optimal_dollar_reward = optimal_position_size * (entry_price - risk_params['TP'])
            sl_pct = ((entry_price - risk_params['SL']) / entry_price) * 100
            tp_pct = ((entry_price - risk_params['TP']) / entry_price) * 100
        
        # Calculate risk/reward for the CURRENT position size (what we actually have)
        if side == 'long':
            current_dollar_risk = current_position_size * (entry_price - risk_params['SL'])
            current_dollar_reward = current_position_size * (risk_params['TP'] - entry_price)
        else:
            current_dollar_risk = current_position_size * (risk_params['SL'] - entry_price)
            current_dollar_reward = current_position_size * (entry_price - risk_params['TP'])
        
        # Use optimal values for risk/reward ratio calculation
        dollar_risk = optimal_dollar_risk
        dollar_reward = optimal_dollar_reward
        rr_ratio = dollar_reward / dollar_risk if dollar_risk > 0 else 0
        
        # Position health assessment
        current_pnl_pct = position.get('percentage', 0)
        if current_pnl_pct < -5:
            position_health = "CRITICAL"
            action_required = "Consider cutting losses or tightening stop"
        elif current_pnl_pct < -2:
            position_health = "WARNING"
            action_required = "Monitor closely, consider reducing size"
        elif current_pnl_pct > 2:
            position_health = "PROFITABLE"
            action_required = "Consider trailing stop or partial profit taking"
        else:
            position_health = "NORMAL"
            action_required = "Set SL/TP as recommended"
        
        return {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'current_price': live_price,
            'position_size': current_position_size,
            'optimal_position_size': optimal_position_size,
            'notional': position['notional'],
            'leverage': leverage,
            'current_pnl': position.get('unrealizedPnl', 0),
            'current_pnl_pct': current_pnl_pct,
            'liquidation_price': liquidation_price,
            
            # Volatility metrics
            'atr': atr,
            'atr_pct': atr_pct,
            'volatility_method': vol_method,
            'sigma_H': primary_sigma,
            'har_sigma_ann': volatility_metrics.get('har_sigma_ann'),
            'garch_sigma_ann': volatility_metrics.get('garch_sigma_ann'),
            
            # Risk management levels
            'stop_loss': risk_params['SL'],
            'take_profit': risk_params['TP'],
            'sl_distance': risk_params['SL_distance'],
            'tp_distance': risk_params['TP_distance'],
            'sl_pct': sl_pct,
            'tp_pct': tp_pct,
            
            # Risk metrics
            'dollar_risk': dollar_risk,
            'dollar_reward': dollar_reward,
            'current_dollar_risk': current_dollar_risk,
            'current_dollar_reward': current_dollar_reward,
            'risk_reward_ratio': rr_ratio,
            'liquidation_buffer_safe': liq_buffer_safe,
            'liquidation_buffer_ratio': liq_buffer_ratio,
            
            # Position assessment
            'position_health': position_health,
            'action_required': action_required,
            'k_multiplier': k_sl,
            'm_multiplier': m_tp,
        }
    
    def _get_default_risk_params(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """Get default risk parameters when volatility analysis fails."""
        entry_price = position['entryPrice']
        side = position['side'].lower()
        leverage = position.get('leverage', 10.0)
        
        # Conservative default: 2% stop loss, 4% take profit
        if side == 'long':
            sl = entry_price * 0.98
            tp = entry_price * 1.04
        else:
            sl = entry_price * 1.02
            tp = entry_price * 0.96
        
        return {
            'symbol': position['symbol'],
            'side': side,
            'entry_price': entry_price,
            'stop_loss': sl,
            'take_profit': tp,
            'volatility_method': 'DEFAULT',
            'position_health': 'UNKNOWN',
            'action_required': 'Manual review required',
            'error': 'Volatility analysis failed - using default parameters'
        }
    
    def analyze_all_positions(self) -> Dict[str, Any]:
        """Analyze all open positions and generate risk metrics."""
        if not self.positions:
            self.fetch_positions()
        
        if not self.positions:
            return {}
        
        print("\n" + "=" * 80)
        print("ANALYZING POSITION RISKS")
        print("=" * 80)
        
        for position in self.positions:
            analysis = self.analyze_position_volatility(position)
            self.risk_analysis[position['symbol']] = analysis
        
        # Calculate portfolio-wide metrics
        portfolio_metrics = self._calculate_portfolio_metrics()
        
        return {
            'positions': self.risk_analysis,
            'portfolio': portfolio_metrics
        }
    
    def _calculate_portfolio_metrics(self) -> Dict[str, Any]:
        """Calculate portfolio-wide risk metrics."""
        total_notional = sum(p['notional'] for p in self.positions)
        total_pnl = sum(p.get('unrealizedPnl', 0) for p in self.positions)
        
        total_dollar_risk = 0
        total_dollar_reward = 0
        positions_at_risk = []
        
        for symbol, analysis in self.risk_analysis.items():
            if 'dollar_risk' in analysis:
                total_dollar_risk += analysis['dollar_risk']
                total_dollar_reward += analysis['dollar_reward']
                
                if analysis.get('position_health') in ['CRITICAL', 'WARNING']:
                    positions_at_risk.append(symbol)
        
        portfolio_rr = total_dollar_reward / total_dollar_risk if total_dollar_risk > 0 else 0
        
        return {
            'total_positions': len(self.positions),
            'total_notional': total_notional,
            'total_unrealized_pnl': total_pnl,
            'total_risk_if_all_sl_hit': total_dollar_risk,
            'total_reward_if_all_tp_hit': total_dollar_reward,
            'portfolio_risk_reward_ratio': portfolio_rr,
            'positions_at_risk': positions_at_risk,
            'risk_pct_of_notional': (total_dollar_risk / total_notional * 100) if total_notional > 0 else 0
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive risk management report."""
        if not self.risk_analysis:
            return "No positions to analyze."
        
        report = []
        report.append("=" * 80)
        report.append("POSITION RISK MANAGEMENT REPORT")
        report.append(f"Generated: {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        report.append("=" * 80)
        
        # Portfolio summary
        portfolio = self.risk_analysis.get('portfolio', {})
        if 'portfolio' in self.risk_analysis:
            report.append("\n📊 PORTFOLIO SUMMARY")
            report.append("-" * 40)
            report.append(f"Total Positions: {portfolio.get('total_positions', 0)}")
            report.append(f"Total Notional: ${portfolio.get('total_notional', 0):,.2f}")
            report.append(f"Total Unrealized PnL: ${portfolio.get('total_unrealized_pnl', 0):,.2f}")
            report.append(f"Total Risk (if all SL hit): ${portfolio.get('total_risk_if_all_sl_hit', 0):,.2f}")
            report.append(f"Total Reward (if all TP hit): ${portfolio.get('total_reward_if_all_tp_hit', 0):,.2f}")
            report.append(f"Portfolio Risk/Reward: {portfolio.get('portfolio_risk_reward_ratio', 0):.2f}:1")
            
            if portfolio.get('positions_at_risk'):
                report.append(f"\n⚠️  Positions at Risk: {', '.join(portfolio['positions_at_risk'])}")
        
        # Individual position analysis
        report.append("\n" + "=" * 80)
        report.append("INDIVIDUAL POSITION ANALYSIS")
        report.append("=" * 80)
        
        for i, position in enumerate(self.positions, 1):
            symbol = position['symbol']
            analysis = self.risk_analysis.get(symbol, {})
            
            if not analysis or 'error' in analysis:
                report.append(f"\nPosition {i}: {symbol}")
                report.append("  ❌ Analysis failed - manual review required")
                continue
            
            # Position header
            report.append(f"\nPosition {i}: {symbol}")
            report.append("-" * 40)
            
            # Current status
            report.append("Current Status:")
            report.append(f"  Entry: ${analysis['entry_price']:.6f} | "
                         f"Current: ${analysis.get('current_price', 0):.6f} | "
                         f"PnL: {analysis.get('current_pnl_pct', 0):.2f}%")
            report.append(f"  Size: {analysis['position_size']} | "
                         f"Notional: ${analysis['notional']:.2f} | "
                         f"Leverage: {analysis['leverage']}x")
            
            if analysis.get('liquidation_price'):
                report.append(f"  Liquidation Price: ${analysis['liquidation_price']:.6f}")
            
            # Volatility analysis
            report.append("\nVolatility Analysis:")
            report.append(f"  Method: {analysis['volatility_method']}")
            report.append(f"  ATR(20): ${analysis.get('atr', 0):.6f} ({analysis.get('atr_pct', 0):.2f}% of price)")
            
            if analysis.get('har_sigma_ann'):
                report.append(f"  HAR-RV σ(annual): {analysis['har_sigma_ann']:.1%}")
            if analysis.get('garch_sigma_ann'):
                report.append(f"  GARCH σ(annual): {analysis['garch_sigma_ann']:.1%}")
            
            # Risk management recommendations
            report.append("\n🎯 Recommended Levels:")
            report.append(f"  STOP LOSS: ${analysis['stop_loss']:.6f} ({analysis['sl_pct']:.2f}% from entry)")
            report.append(f"    💰 Optimal Risk: ${analysis['dollar_risk']:.2f} (for optimal size: {analysis.get('optimal_position_size', 0):.2f})")
            report.append(f"    💰 Current Risk: ${analysis.get('current_dollar_risk', 0):.2f} (for current size: {analysis['position_size']:.2f})")
            
            if analysis.get('liquidation_buffer_safe') is not None:
                if analysis['liquidation_buffer_safe']:
                    report.append(f"    ✅ Safe from liquidation")
                else:
                    report.append(f"    ⚠️  TOO CLOSE TO LIQUIDATION!")
            
            report.append(f"  TAKE PROFIT: ${analysis['take_profit']:.6f} ({analysis['tp_pct']:.2f}% from entry)")
            report.append(f"    💰 Optimal Reward: ${analysis['dollar_reward']:.2f}")
            report.append(f"    💰 Current Reward: ${analysis.get('current_dollar_reward', 0):.2f}")
            report.append(f"    📊 Risk/Reward: {analysis['risk_reward_ratio']:.2f}:1")
            
            # Check if position size is significantly different from optimal
            if analysis.get('optimal_position_size'):
                size_ratio = analysis['position_size'] / analysis['optimal_position_size']
                if size_ratio > 1.5:
                    report.append(f"    ⚠️  POSITION SIZE TOO LARGE: Current is {size_ratio:.1f}x optimal")
                elif size_ratio < 0.5:
                    report.append(f"    ℹ️  POSITION SIZE SMALL: Current is {size_ratio:.1f}x optimal")
            
            # Position assessment
            health_emoji = {
                'CRITICAL': '🔴',
                'WARNING': '🟡',
                'NORMAL': '🟢',
                'PROFITABLE': '💚',
                'UNKNOWN': '⚪'
            }
            
            report.append("\nRisk Assessment:")
            report.append(f"  Status: {health_emoji.get(analysis['position_health'], '⚪')} "
                         f"{analysis['position_health']}")
            report.append(f"  Action: {analysis['action_required']}")
        
        # Final recommendations
        report.append("\n" + "=" * 80)
        report.append("RECOMMENDATIONS")
        report.append("=" * 80)
        
        if portfolio.get('positions_at_risk'):
            report.append("⚠️  IMMEDIATE ATTENTION REQUIRED:")
            for symbol in portfolio['positions_at_risk']:
                analysis = self.risk_analysis.get(symbol, {})
                report.append(f"  • {symbol}: {analysis.get('action_required', 'Review position')}")
        
        report.append("\n✅ GENERAL GUIDELINES:")
        report.append("  1. Set all stop losses immediately to protect capital")
        report.append("  2. Monitor high-leverage positions (15x+) closely")
        report.append("  3. Consider trailing stops for profitable positions")
        report.append("  4. Review positions with poor risk/reward ratios (<1.5:1)")
        
        return "\n".join(report)
    
    def export_to_json(self, filename: str = "risk_analysis.json"):
        """Export risk analysis to JSON file."""
        output = {
            'timestamp': dt.datetime.now(dt.timezone.utc).isoformat(),
            'positions': self.risk_analysis,
            'portfolio': self._calculate_portfolio_metrics() if self.risk_analysis else {}
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\nRisk analysis exported to {filename}")


def main():
    """Main execution function."""
    # Initialize risk manager
    manager = PositionRiskManager(sandbox=False)
    
    # Fetch and analyze positions
    positions = manager.fetch_positions()
    
    if not positions:
        print("No positions to analyze. Exiting.")
        return
    
    # Analyze all positions
    manager.analyze_all_positions()
    
    # Generate and print report
    report = manager.generate_report()
    print("\n" + report)
    
    # Export to JSON
    manager.export_to_json()
    
    # Print summary table
    print("\n" + "=" * 80)
    print("QUICK REFERENCE TABLE")
    print("=" * 80)
    print(f"{'Symbol':<15} {'Side':<5} {'Entry':<10} {'SL':<10} {'TP':<10} {'R:R':<6} {'Health'}")
    print("-" * 80)
    
    for position in positions:
        symbol = position['symbol']
        analysis = manager.risk_analysis.get(symbol, {})
        
        if analysis and 'stop_loss' in analysis:
            print(f"{symbol:<15} {analysis['side'].upper():<5} "
                  f"${analysis['entry_price']:<9.4f} "
                  f"${analysis['stop_loss']:<9.4f} "
                  f"${analysis['take_profit']:<9.4f} "
                  f"{analysis['risk_reward_ratio']:<5.1f}:1 "
                  f"{analysis['position_health']}")


if __name__ == "__main__":
    main()
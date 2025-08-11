# Advanced Crypto Position Risk Management System

A comprehensive cryptocurrency trading risk management system that combines real-time position monitoring with advanced volatility analysis using GARCH and HAR-RV models, plus portfolio correlation analysis.

## 🎯 Overview

This system provides sophisticated risk management for cryptocurrency trading by:

- **Real-time Position Monitoring**: Fetches live positions from Bybit
- **Advanced Volatility Analysis**: Uses GARCH(1,1) and HAR-RV models for volatility forecasting
- **Dynamic SL/TP Calculation**: Calculates optimal stop-loss and take-profit levels based on volatility
- **Position Sizing**: Recommends optimal position sizes based on target risk
- **Portfolio Risk Assessment**: Analyzes overall portfolio risk and provides actionable recommendations
- **Correlation Analysis**: Identifies correlated positions and applies cluster risk caps
- **Configuration Management**: Dynamic settings loading with fallback to defaults

## 📁 Project Structure

```
market_analysis/
├── position_risk_manager.py    # Main risk management system
├── garch_vol_triggers.py       # GARCH and HAR-RV volatility models
├── get_position.py             # Position fetching utilities
├── atr_sl_gpt.py              # ATR-based risk management
├── requirements.txt           # Python dependencies
├── settings.toml             # Configuration file (create from settings.example.toml)
├── settings.example.toml     # Example configuration
├── risk_analysis.json        # Generated risk analysis output
└── README.md                 # This file
```

## 🚀 Quick Start

### Installation

```bash
# Clone and setup
git clone <repository>
cd market_analysis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Copy `settings.example.toml` to `settings.toml`
2. Add your Bybit API credentials:
```toml
[bybit]
api_key = "your_api_key"
api_secret = "your_api_secret"
sandbox = false  # Set to true for testnet
```

### Run Position Risk Analysis

```bash
python position_risk_manager.py
```

## 🔧 Core Components & Logic Flow

### 1. Position Risk Manager (`position_risk_manager.py`)

The main system orchestrates the entire risk analysis workflow:

**Logic Flow:**
```
1. Initialize → Load Configuration → Fetch Positions
2. For each position:
   a. Analyze volatility (GARCH + HAR-RV + ATR blend)
   b. Calculate optimal SL/TP levels
   c. Determine position sizing recommendations
   d. Assess position health
3. Calculate portfolio metrics
4. Apply correlation analysis and cluster risk caps
5. Generate comprehensive report
6. Export to JSON
```

**Key Features:**
- **Configuration Loading**: Dynamic settings with fallback to defaults
- **Multi-Model Volatility**: Blends GARCH, HAR-RV, and ATR for robust estimates
- **Dynamic Risk Parameters**: Adjusts SL/TP multipliers based on leverage
- **Portfolio Correlation**: Identifies correlated positions and caps cluster risk
- **Health Assessment**: Categorizes positions as NORMAL/WARNING/CRITICAL/PROFITABLE
- **JSON Export**: Saves analysis for external processing

**Output Example:**
```
Position 1: EXMPL/USDT:USDT
----------------------------------------
Current Status:
  Entry: $1.000000 | Current: $1.012000 | PnL: 0.56%
  Size: 500.0 | Notional: $500.00 | Leverage: 15.0x

Volatility Analysis:
  Method: VOL_BLEND (GARCH 30% + HAR 40% + ATR 30%)
  ATR(20): $0.014500 (1.46% of price)
  HAR-RV σ(annual): 16.2%
  GARCH σ(annual): 93.3%
  Blended σ(4h): 2.1%

🎯 Recommended Levels:
  STOP LOSS: $0.985000 (-0.35% from entry)
    💰 Optimal Risk: $3.08 (for optimal size: 1200.00)
    💰 Current Risk: $0.53 (for current size: 500.00)
    ✅ Safe from liquidation
  TAKE PROFIT: $1.030000 (0.69% from entry)
    💰 Optimal Reward: $6.11
    💰 Current Reward: $1.06
    📊 Risk/Reward: 1.98:1
    ℹ️  POSITION SIZE SMALL: Current is 0.2x optimal

Risk Assessment:
  Status: 🟢 NORMAL
  Action: Set SL/TP as recommended
```

### 2. GARCH Volatility Triggers (`garch_vol_triggers.py`)

Advanced volatility analysis using multiple models:

**Volatility Models:**

#### GARCH(1,1) Model
- Models volatility clustering and mean reversion
- Provides short-term volatility forecasts
- More sensitive to recent market conditions
- Weight: 30% in blended estimate

#### HAR-RV (Heterogeneous Autoregressive Realized Volatility)
- Uses realized volatility from different time horizons
- More stable long-term volatility estimates
- Better for trend-following strategies
- Weight: 40% in blended estimate

#### ATR (Average True Range)
- Simple volatility measure based on price ranges
- Used as fallback when advanced models fail
- Good for quick volatility assessment
- Weight: 30% in blended estimate

**Blending Logic:**
```python
# Outlier detection and blending
if garch_sigma and har_sigma:
    ratio = garch_sigma / har_sigma
    if ratio > outlier_threshold:
        # Use HAR if GARCH is outlier
        blended_sigma = har_sigma
    else:
        # Weighted blend
        blended_sigma = (w_garch * garch_sigma + 
                        w_har * har_sigma + 
                        w_atr * atr_sigma)
else:
    # Fallback to ATR
    blended_sigma = atr_sigma
```

### 3. Portfolio Correlation Analysis

**New Feature**: Automatically identifies correlated positions and applies risk caps:

```python
# Correlation clustering algorithm
1. Fetch 4h returns for all positions (60-day lookback)
2. Calculate correlation matrix
3. Group positions with |correlation| ≥ 0.7 into clusters
4. Cap total cluster risk at 50% of portfolio risk budget
5. Scale down cluster members proportionally
```

**Example Output:**
```
📊 PORTFOLIO SUMMARY
----------------------------------------
Total Positions: 5
Total Notional: $2,450.33
Total Unrealized PnL: $45.67
Total Risk (if all SL hit): $89.23
Total Reward (if all TP hit): $156.78
Portfolio Risk/Reward: 1.76:1

⚠️  Positions at Risk: BTC/USDT:USDT, ETH/USDT:USDT
```

## 📊 Understanding the Outputs

### Position Analysis Breakdown

#### 1. Current Status
```
Entry: $1.000000 | Current: $1.012000 | PnL: 0.56%
Size: 500.0 | Notional: $500.00 | Leverage: 15.0x
```
- **Entry**: Position entry price
- **Current**: Live market price
- **PnL**: Unrealized profit/loss percentage
- **Size**: Position size in base currency
- **Notional**: Position value in USDT
- **Leverage**: Current leverage used

#### 2. Volatility Analysis
```
Method: VOL_BLEND (GARCH 30% + HAR 40% + ATR 30%)
ATR(20): $0.014500 (1.46% of price)
HAR-RV σ(annual): 16.2%
GARCH σ(annual): 93.3%
Blended σ(4h): 2.1%
```
- **Method**: Shows the blending approach used
- **ATR(20)**: 20-period Average True Range in dollars and percentage
- **HAR-RV σ**: Annualized volatility from HAR-RV model
- **GARCH σ**: Annualized volatility from GARCH model
- **Blended σ**: Final volatility estimate used for calculations

#### 3. Risk Management Levels
```
STOP LOSS: $0.985000 (-0.35% from entry)
  💰 Optimal Risk: $3.08 (for optimal size: 1200.00)
  💰 Current Risk: $0.53 (for current size: 500.00)
  ✅ Safe from liquidation

TAKE PROFIT: $1.030000 (0.69% from entry)
  💰 Optimal Reward: $6.11
  💰 Current Reward: $1.06
  📊 Risk/Reward: 1.98:1
```
- **SL/TP Levels**: Calculated based on volatility and multipliers
- **Optimal Risk/Reward**: Based on optimal position size for target risk
- **Current Risk/Reward**: Based on actual position size
- **Risk/Reward Ratio**: Reward divided by risk (target: >1.5:1)

#### 4. Position Health Assessment
- **🟢 NORMAL**: Position within normal parameters
- **🟡 WARNING**: Position needs attention (PnL < -2%)
- **🔴 CRITICAL**: Position needs immediate action (PnL < -5%)
- **💚 PROFITABLE**: Position in profit, consider trailing stops

### Risk/Reward Calculation Logic

The system calculates risk/reward using **optimal position sizing**:

1. **Target Risk**: Configurable (default 2.5% of position notional)
2. **Volatility Forecast**: Uses blended GARCH/HAR-RV/ATR models
3. **SL Distance**: `k × σ_H × entry_price` (k = 0.8-1.8 based on leverage)
4. **TP Distance**: `m × σ_H × entry_price` (m = 1.8-4.0 based on leverage)
5. **Optimal Size**: `target_risk / sl_distance`
6. **Risk/Reward**: `tp_distance / sl_distance`

### Position Sizing Recommendations

The system compares current vs optimal position sizes:

- **Current < 0.5× Optimal**: Position too small for proper risk management
- **Current > 1.5× Optimal**: Position too large, consider reducing
- **0.5× ≤ Current ≤ 1.5× Optimal**: Position size appropriate

## 🎛️ Configuration Options

### Risk Parameters

```toml
[risk]
base_target_pct = 0.025      # Base risk target (2.5%)
min_target_pct = 0.015       # Minimum risk target (1.5%)
max_target_pct = 0.040       # Maximum risk target (4.0%)
use_dynamic = true           # Enable dynamic risk adjustment

[stops]
# Leverage-based SL multipliers
k_sl_lev20 = 1.0            # Very tight stop for high leverage
k_sl_lev15 = 1.2            # Medium leverage
k_sl_lev10 = 1.5            # Lower leverage
k_sl_low   = 1.8            # Low leverage

# Leverage-based TP multipliers
m_tp_lev20 = 2.6            # Conservative target for high leverage
m_tp_lev15 = 3.0            # Medium leverage
m_tp_lev10 = 3.5            # Lower leverage
m_tp_low   = 4.0            # Aggressive target for low leverage
```

### Volatility Analysis Settings

```toml
[vol]
blend_w_garch = 0.30        # GARCH weight in blend
blend_w_har   = 0.40        # HAR-RV weight in blend
blend_w_atr   = 0.30        # ATR weight in blend
garch_har_outlier_ratio = 2.0  # Outlier detection threshold
horizon_hours = 4           # Volatility forecast horizon
```

### Portfolio Correlation Settings

```toml
[portfolio]
corr_lookback_days = 60     # Days for correlation calculation
corr_threshold = 0.7        # Correlation threshold for clustering
cluster_risk_cap_pct = 0.5  # Max risk per cluster (% of total)
```

## 📈 Usage Examples

### 1. Basic Position Analysis
```bash
python position_risk_manager.py
```

### 2. Custom Volatility Analysis
```python
from garch_vol_triggers import analyze_multiple_symbols_bybit

# Analyze multiple symbols
symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
results = analyze_multiple_symbols_bybit(symbols, timeframe="4h", days_back=90)
```

### 3. Individual Symbol Analysis
```python
from garch_vol_triggers import get_klines_bybit, garch_sigma_ann_and_sigma_H

# Get data and analyze
df = get_klines_bybit("BTC/USDT", "1h", days_back=30)
sigma_ann, sigma_H, garch_res = garch_sigma_ann_and_sigma_H(df["close"])
```

### 4. Configuration Management
```python
from position_risk_manager import load_settings

# Load configuration with fallback
cfg = load_settings("settings.toml")
risk_target = cfg.get('risk', {}).get('base_target_pct', 0.025)
```

## 🔍 Troubleshooting

### Common Issues

1. **"No module named 'pandas'"**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **"Error fetching data from Bybit"**
   - Check API credentials in `settings.toml`
   - Verify internet connection
   - Check if using correct symbol format (e.g., "BTC/USDT:USDT" for Bybit)

3. **"GARCH failed"**
   - Need at least 500 data points for stable GARCH fit
   - Try increasing `lookback_days` parameter

4. **"HAR-RV failed"**
   - Need sufficient historical data
   - Try different timeframe or longer lookback period

5. **"Configuration not found"**
   - Copy `settings.example.toml` to `settings.toml`
   - System will use defaults if no config file exists

### Performance Tips

- Use `sandbox=True` for testing
- Reduce `lookback_days` for faster analysis
- Cache volatility calculations for frequently analyzed symbols
- Adjust correlation settings for your portfolio size

## 📚 Technical Details

### Volatility Models

#### GARCH(1,1) Model
```
σ²_t = ω + α₁r²_{t-1} + β₁σ²_{t-1}
```
Where:
- `σ²_t`: Conditional variance at time t
- `r²_{t-1}`: Squared return at time t-1
- `ω, α₁, β₁`: Model parameters

#### HAR-RV Model
```
log(RV_{t+1}) = c + β_D log(RV_D) + β_W log(RV_W) + β_M log(RV_M)
```
Where:
- `RV_D`: Daily realized volatility
- `RV_W`: Weekly realized volatility  
- `RV_M`: Monthly realized volatility

### Risk Calculation Formula

```
SL_distance = k × σ_H × entry_price
TP_distance = m × σ_H × entry_price
Optimal_Size = target_risk / SL_distance
```

Where `σ_H` is the volatility forecast for the target horizon.

### Correlation Analysis Algorithm

```
1. Fetch 4h returns for all positions (configurable lookback)
2. Calculate pairwise correlation matrix
3. Apply threshold-based clustering:
   - Start with each symbol as its own cluster
   - Merge clusters if any member has |corr| ≥ threshold
4. For each cluster:
   - Calculate total cluster risk
   - If cluster risk > cap_pct × total_risk:
     - Scale down all cluster members proportionally
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Cryptocurrency trading involves substantial risk of loss. Always:
- Test thoroughly on paper trading first
- Never risk more than you can afford to lose
- Verify all calculations independently
- Consider professional financial advice

The authors are not responsible for any financial losses incurred through the use of this software.

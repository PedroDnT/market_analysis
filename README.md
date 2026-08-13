# Crypto Position Risk Manager

Analysis-only toolkit for crypto perpetual positions. It pulls live Bybit positions, forecasts volatility with a GARCH / HAR-RV / ATR blend, and recommends stop-loss, take-profit, and size. Nothing is executed.

## Quick start

```bash
git clone <repository>
cd <repository-folder>
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

Copy `settings.example.toml` to `settings.toml` and create a `.env` in the repo root:

```
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
```

Do not commit `settings.toml`, `.env`, or run outputs such as `risk_analysis.json`.

```bash
risk-manager
```

Docker:

```bash
docker build -t risk-manager-app .
docker run --rm \
  -v "$(pwd)/.env":/app/.env \
  -v "$(pwd)/settings.toml":/app/settings.toml \
  risk-manager-app
```

Tests:

```bash
pip install -e ".[test]"
pytest -v
```

## Structure

```
market_analysis/
├── __main__.py                 # CLI entry (`risk-manager`)
├── position_risk_manager.py    # Orchestrates fetch, analysis, report
├── garch_vol_triggers.py       # GARCH, HAR-RV, ATR blend
├── atr_sl_gpt.py               # ATR stops and trailing
├── get_position.py             # Bybit position fetch
├── confidence.py               # Setup quality score
├── reporting.py                # Report text and portfolio metrics
├── config.py                   # settings.toml loader
└── utils.py
settings.example.toml           # Copy to settings.toml (gitignored)
```

Generated `risk_analysis.json` is a local export only; it is gitignored because it contains live account data.

## Configuration

`settings.toml` (from `settings.example.toml`):

```toml
[risk]
base_target_pct = 0.025
min_target_pct = 0.020
max_target_pct = 0.030
use_dynamic = true

[stops]
k_sl_lev20 = 1.5
k_sl_lev15 = 1.8
k_sl_lev10 = 2.2
k_sl_low   = 2.5
m_tp_lev20 = 3.0
m_tp_lev15 = 3.5
m_tp_lev10 = 4.0
m_tp_low   = 4.5

[vol]
blend_w_garch = 0.30
blend_w_har   = 0.40
blend_w_atr   = 0.30
garch_har_outlier_ratio = 2.0
horizon_hours = 4

[portfolio]
corr_lookback_days = 60
corr_threshold = 0.7
cluster_risk_cap_pct = 0.5
```

- **Risk:** fraction of notional to put at risk. With `use_dynamic`, the target scales with a confidence score (about 0.8x to 1.2x), then clipped to `min_target_pct` / `max_target_pct`.
- **Stops:** `k` (SL) and `m` (TP) multipliers on the horizon volatility `sigma_H`. Higher leverage uses tighter `k` / `m`.
- **Vol blend:** 30% GARCH, 40% HAR-RV, 30% ATR. If GARCH / HAR diverge past `garch_har_outlier_ratio`, HAR is used alone; otherwise ATR is the fallback.
- **Portfolio:** positions with |correlation| >= 0.7 are clustered; cluster risk is capped at 50% of the portfolio budget.

API keys can live in `settings.toml` or `.env`. Both files are gitignored.

## How it works

1. Load config, fetch open positions.
2. For each position, blend GARCH / HAR-RV / ATR, set SL/TP from leverage-adjusted `k`/`m`, and compare current size to `target_risk / sl_distance`.
3. Score the setup (EMA trend, Donchian breakout, vol regime, RSI-style momentum, GARCH/HAR agreement). Score range is -2 to +5 and feeds the dynamic risk target and stop/target tweaks.
4. Cluster correlated names, cap cluster risk, classify health (NORMAL / WARNING / CRITICAL / PROFITABLE), print a report, export JSON locally.

```
SL_distance = k * sigma_H * entry
TP_distance = m * sigma_H * entry
optimal_size = target_risk / SL_distance
```

Size flags: below 0.5x optimal is small; above 1.5x is large.

Example (synthetic):

```
Position 1: EXMPL/USDT:USDT
----------------------------------------
Current Status:
  Entry: $1.000000 | Current: $1.012000 | PnL: 1.20%
  Size: 500.0 | Notional: $500.00 | Leverage: 10.0x

Volatility Analysis:
  Method: VOL_BLEND (GARCH 30% + HAR 40% + ATR 30%)
  ATR(20): $0.014500 (1.45% of price)
  HAR-RV sigma(annual): 16.2%
  GARCH sigma(annual): 93.3%
  Blended sigma(4h): 2.1%

Recommended Levels:
  STOP LOSS: $0.985000 (-1.50% from entry)
    Optimal Risk: $18.00 (for optimal size: 1200.00)
    Current Risk: $7.50 (for current size: 500.00)
    Safe from liquidation
  TAKE PROFIT: $1.030000 (3.00% from entry)
    Optimal Reward: $36.00
    Current Reward: $15.00
    Risk/Reward: 2.00:1
    POSITION SIZE SMALL: Current is 0.4x optimal

Risk Assessment:
  Status: NORMAL
  Action: Set SL/TP as recommended
```

## Troubleshooting

- Missing packages: activate the venv and `pip install -e .` (or `pip install -r requirements.txt`).
- Bybit fetch errors: check `.env` / `settings.toml` and symbol format (`BTC/USDT:USDT`).
- GARCH/HAR failures: increase lookback; GARCH wants hundreds of bars. ATR is the fallback.
- Missing config: copy `settings.example.toml` to `settings.toml`; defaults apply if the file is absent.

## License

MIT. See `LICENSE`.

This software is for research. Derivatives trading can lose more than the margin you post. Verify outputs yourself; the authors are not responsible for losses.

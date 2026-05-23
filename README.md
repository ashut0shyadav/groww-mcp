# Groww MCP Server

An MCP (Model Context Protocol) server that connects Claude to Groww's official Trade API. Search stocks, analyze prices with technical indicators, and execute trades — all through natural language.

## What it does

Tell Claude things like:
- "What's the current price of RELIANCE?"
- "Compute RSI and MACD for INFY over the last month"
- "Buy 1 share of TCS at market price"
- "Analyze HDFC — if RSI is below 30, buy 1 share"

Claude calls the MCP tools, which hit Groww's real API for market data and (optionally) execute real trades.

## Tools Available (14)

| Category | Tools |
|----------|-------|
| Market Data | `search_instrument`, `get_quote`, `get_ltp`, `get_ohlc`, `get_historical_candles`, `get_option_chain` |
| Analysis | `get_technical_indicators` (RSI, MACD, EMA, SMA, Bollinger Bands, ADX, VWAP, Stochastic, ATR, OBV) |
| Portfolio | `get_holdings`, `get_positions`, `get_orders`, `get_order_status` |
| Trading | `place_order`, `modify_order`, `cancel_order` |

## Safety Features

- **Paper trading mode** (default ON) — simulates orders without hitting the exchange
- **Max order value cap** — configurable per-order limit (default ₹10,000)
- **Daily spend cap** — total daily trading limit (default ₹50,000)
- **Market hours check** — rejects orders outside 9:15 AM – 3:30 PM IST
- **F&O restriction** — derivatives disabled by default

---

## Setup

### Prerequisites

- Python 3.11+ (tested with 3.12)
- A Groww Demat + Trading account
- Claude Code CLI installed

### 1. Clone and install

```bash
git clone https://github.com/ashut0shyadav/groww-mcp.git
cd groww-mcp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Get Groww API credentials

1. Go to https://groww.in/trade-api/api-keys
2. Click **Get API Key** — save the key
3. Enable **TOTP authentication** in the Trade API settings
4. Save the TOTP secret (base32 string — uppercase letters A-Z and digits 2-7 only)

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
GROWW_API_KEY=your_api_key_here
GROWW_TOTP_SECRET=your_base32_totp_secret_here

# Safety Settings
PAPER_TRADING=true
MAX_ORDER_VALUE=10000
MAX_DAILY_SPEND=50000
ALLOW_FNO=false
```

### 4. Verify credentials

```bash
python scripts/test_connection.py
```

Expected output:
```
Connecting to Groww API...
  ✓ Authentication successful
Fetching LTP for RELIANCE...
  ✓ LTP for RELIANCE: ₹1354.5
Fetching instruments list...
  ✓ 173019 instruments loaded
✓ All checks passed — server is ready for Claude Code integration.
```

### 5. Register with Claude Code

```bash
claude mcp add groww-trading \
  --transport stdio \
  -- /path/to/groww-mcp/.venv/bin/python -m src.server
```

Replace `/path/to/groww-mcp` with your actual clone path.

### 6. Start using

Open a new Claude Code session and try:
```
Search for Reliance Industries
Get RSI and MACD for INFY over the last month
Buy 1 share of TCS at market price
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GROWW_API_KEY` | (required) | Your Groww Trade API key |
| `GROWW_TOTP_SECRET` | (required) | Base32 TOTP secret for authentication |
| `PAPER_TRADING` | `true` | Simulate trades without real orders |
| `MAX_ORDER_VALUE` | `10000` | Max value (₹) per single order |
| `MAX_DAILY_SPEND` | `50000` | Max total order value (₹) per day |
| `ALLOW_FNO` | `false` | Allow Futures & Options trading |

---

## Going Live (Real Money)

When you're ready to place real orders:

1. Set `PAPER_TRADING=false` in `.env`
2. Set a low `MAX_ORDER_VALUE` (e.g., `500`) to start safe
3. Test with a cheap stock (IDEA is ~₹8/share)
4. Verify the order appears in your Groww mobile app

---

## Running Tests

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest tests/ -v
```

41 tests covering all modules — auth, safety, market data, analysis, portfolio, and trading.

---

## Architecture

```
Claude Code ──stdio──▶ MCP Server ──HTTPS──▶ Groww Trade API (api.groww.in)
                            │
                     ┌──────┼──────┐
                     │      │      │
                  Market  Trading  Analysis
                  Tools   Tools    Tools
                     │      │
                     │   Safety Layer
                     │   (caps, paper mode)
                     │
                  growwapi SDK + pyotp auth
```

## Rate Limits (Groww-enforced)

| Type | Per Second | Per Minute |
|------|-----------|-----------|
| Orders (create/modify/cancel) | 10 | 250 |
| Live Data (quote/LTP/OHLC) | 10 | 300 |
| Non-Trading (positions/holdings) | 20 | 500 |

---

## Tech Stack

- **Python 3.12** + `mcp` SDK (FastMCP with stdio transport)
- **growwapi** — Groww's official Python SDK
- **pandas-ta** — 130+ technical indicators
- **pyotp** — TOTP-based authentication (no daily manual approval)

## License

MIT

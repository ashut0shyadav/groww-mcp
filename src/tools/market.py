"""MCP tools for market data (instruments, quotes, OHLC, options)."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from src.auth import get_client

IST = ZoneInfo("Asia/Kolkata")

_instruments_cache = {"df": None}


def register_market_tools(mcp: FastMCP):
    """Register all market-data tools on the given MCP server instance."""

    def _get_instruments():
        if _instruments_cache["df"] is None:
            groww = get_client()
            _instruments_cache["df"] = groww.get_all_instruments()
        return _instruments_cache["df"]

    @mcp.tool()
    async def search_instrument(query: str, exchange: str = "NSE") -> str:
        """Search for instruments by partial name or trading symbol match.

        Returns the top 10 matching instruments as JSON. Useful for finding
        the exact trading_symbol before fetching quotes or historical data.

        Args:
            query: Partial name or symbol to search for (case-insensitive).
            exchange: Exchange to search on (default: NSE).
        """
        try:
            df = _get_instruments()

            if "exchange" in df.columns:
                df = df[df["exchange"].str.upper() == exchange.upper()]

            mask = (
                df["trading_symbol"].str.contains(query, case=False, na=False)
                | df["name"].str.contains(query, case=False, na=False)
            )
            matches = df[mask].head(10)

            results = matches.to_dict(orient="records")
            return json.dumps(results, indent=2, default=str)
        except Exception as e:
            return f"Error searching instruments: {e}"

    @mcp.tool()
    async def get_quote(
        trading_symbol: str, exchange: str = "NSE", segment: str = "CASH"
    ) -> str:
        """Get a full quote for a single instrument.

        Returns detailed market data including last price, bid/ask, volume,
        open/high/low/close, and other trading information.

        Args:
            trading_symbol: The trading symbol (e.g. "RELIANCE", "NIFTY").
            exchange: Exchange (default: NSE).
            segment: Market segment (default: CASH).
        """
        try:
            groww = get_client()

            exchange_val = getattr(groww, f"EXCHANGE_{exchange.upper()}", exchange)
            segment_val = getattr(groww, f"SEGMENT_{segment.upper()}", segment)

            quote = groww.get_quote(
                exchange=exchange_val,
                segment=segment_val,
                trading_symbol=trading_symbol.upper(),
            )
            return json.dumps(quote, indent=2, default=str)
        except Exception as e:
            return f"Error fetching quote for {trading_symbol}: {e}"

    @mcp.tool()
    async def get_ltp(symbols: list[str], segment: str = "CASH") -> str:
        """Get the Last Traded Price for up to 50 instruments at once.

        Args:
            symbols: List of trading symbols (e.g. ["RELIANCE", "INFY", "TCS"]).
                     Maximum 50 symbols per request.
            segment: Market segment (default: CASH).
        """
        try:
            groww = get_client()

            segment_val = getattr(groww, f"SEGMENT_{segment.upper()}", segment)

            # Prefix each symbol with NSE_
            exchange_trading_symbols = tuple(
                f"NSE_{s.upper()}" for s in symbols[:50]
            )

            prices = groww.get_ltp(
                segment=segment_val,
                exchange_trading_symbols=exchange_trading_symbols,
            )
            return json.dumps(prices, indent=2, default=str)
        except Exception as e:
            return f"Error fetching LTP: {e}"

    @mcp.tool()
    async def get_ohlc(symbols: list[str], segment: str = "CASH") -> str:
        """Get Open/High/Low/Close data for up to 50 instruments at once.

        Args:
            symbols: List of trading symbols (e.g. ["RELIANCE", "INFY"]).
                     Maximum 50 symbols per request.
            segment: Market segment (default: CASH).
        """
        try:
            groww = get_client()

            segment_val = getattr(groww, f"SEGMENT_{segment.upper()}", segment)

            exchange_trading_symbols = tuple(
                f"NSE_{s.upper()}" for s in symbols[:50]
            )

            ohlc = groww.get_ohlc(
                segment=segment_val,
                exchange_trading_symbols=exchange_trading_symbols,
            )
            return json.dumps(ohlc, indent=2, default=str)
        except Exception as e:
            return f"Error fetching OHLC: {e}"

    @mcp.tool()
    async def get_historical_candles(
        trading_symbol: str,
        interval_minutes: int = 1440,
        days_back: int = 30,
        exchange: str = "NSE",
        segment: str = "CASH",
    ) -> str:
        """Get historical candlestick (OHLCV) data for an instrument.

        Returns candle data with human-readable timestamps. Each candle contains:
        [timestamp, open, high, low, close, volume].

        Args:
            trading_symbol: The trading symbol (e.g. "RELIANCE").
            interval_minutes: Candle interval in minutes (e.g. 1, 5, 15, 60, 1440 for daily).
                             Default is 1440 (daily candles).
            days_back: Number of days of history to fetch (default: 30).
            exchange: Exchange (default: NSE).
            segment: Market segment (default: CASH).
        """
        try:
            groww = get_client()

            exchange_val = getattr(groww, f"EXCHANGE_{exchange.upper()}", exchange)
            segment_val = getattr(groww, f"SEGMENT_{segment.upper()}", segment)

            now = datetime.now(IST)
            end_time = now.strftime("%Y-%m-%d %H:%M:%S")
            start_time = (now - timedelta(days=days_back)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            data = groww.get_historical_candle_data(
                trading_symbol=trading_symbol.upper(),
                exchange=exchange_val,
                segment=segment_val,
                start_time=start_time,
                end_time=end_time,
                interval_in_minutes=interval_minutes,
            )

            # Format candles with human-readable timestamps
            candles = data.get("candles", [])
            formatted = []
            for candle in candles:
                formatted.append(
                    {
                        "timestamp": candle[0],
                        "open": candle[1],
                        "high": candle[2],
                        "low": candle[3],
                        "close": candle[4],
                        "volume": candle[5] if len(candle) > 5 else None,
                    }
                )

            result = {
                "trading_symbol": trading_symbol.upper(),
                "exchange": exchange,
                "interval_minutes": interval_minutes,
                "start_time": start_time,
                "end_time": end_time,
                "candle_count": len(formatted),
                "candles": formatted,
            }
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            return f"Error fetching historical candles for {trading_symbol}: {e}"

    @mcp.tool()
    async def get_option_chain(
        underlying: str, expiry_date: str, exchange: str = "NSE"
    ) -> str:
        """Get the option chain with Greeks for a given underlying and expiry.

        Returns all call and put options for the specified underlying instrument
        and expiry date, including Greeks (delta, gamma, theta, vega) if available.

        Args:
            underlying: The underlying instrument symbol (e.g. "NIFTY", "BANKNIFTY").
            expiry_date: Expiry date in YYYY-MM-DD format (e.g. "2025-11-28").
            exchange: Exchange (default: NSE).
        """
        try:
            groww = get_client()

            exchange_val = getattr(groww, f"EXCHANGE_{exchange.upper()}", exchange)

            chain = groww.get_option_chain(
                exchange=exchange_val,
                underlying=underlying.upper(),
                expiry_date=expiry_date,
            )
            return json.dumps(chain, indent=2, default=str)
        except Exception as e:
            return f"Error fetching option chain for {underlying}: {e}"

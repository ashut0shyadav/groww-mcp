"""MCP tools for technical analysis on stock price data."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_ta as ta
from mcp.server.fastmcp import FastMCP

from src.auth import get_client

IST = ZoneInfo("Asia/Kolkata")

SUPPORTED_INDICATORS = [
    "RSI", "MACD", "EMA", "SMA", "BBANDS", "ADX", "VWAP", "STOCH", "ATR", "OBV"
]


def register_analysis_tools(mcp: FastMCP):

    @mcp.tool()
    async def get_technical_indicators(
        trading_symbol: str,
        indicators: list[str],
        interval_minutes: int = 1440,
        days_back: int = 60,
        exchange: str = "NSE",
        segment: str = "CASH",
    ) -> str:
        """Compute technical indicators for a stock using historical price data.

        Fetches OHLCV candles and computes the requested indicators. Returns the
        most recent values for each indicator plus a summary for quick analysis.

        Supported indicators: RSI, MACD, EMA, SMA, BBANDS (Bollinger Bands),
        ADX, VWAP, STOCH (Stochastic), ATR, OBV.

        Args:
            trading_symbol: The stock symbol (e.g. "RELIANCE", "INFY").
            indicators: List of indicator names to compute (e.g. ["RSI", "MACD", "EMA"]).
            interval_minutes: Candle interval - 1, 5, 15, 60, 1440 (daily). Default: 1440.
            days_back: Days of history to analyze (default: 60, more data = better signals).
            exchange: Exchange (default: NSE).
            segment: Market segment (default: CASH).
        """
        try:
            groww = get_client()

            exchange_val = getattr(groww, f"EXCHANGE_{exchange.upper()}", exchange)
            segment_val = getattr(groww, f"SEGMENT_{segment.upper()}", segment)

            now = datetime.now(IST)
            end_time = now.strftime("%Y-%m-%d %H:%M:%S")
            start_time = (now - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")

            data = groww.get_historical_candle_data(
                trading_symbol=trading_symbol.upper(),
                exchange=exchange_val,
                segment=segment_val,
                start_time=start_time,
                end_time=end_time,
                interval_in_minutes=interval_minutes,
            )

            candles = data.get("candles", [])
            if not candles:
                return json.dumps({"error": "No candle data returned"})

            df = pd.DataFrame(
                candles, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df = df.sort_values("timestamp").reset_index(drop=True)

            results = {
                "trading_symbol": trading_symbol.upper(),
                "interval_minutes": interval_minutes,
                "candle_count": len(df),
                "latest_close": float(df["close"].iloc[-1]),
                "indicators": {},
            }

            for ind in indicators:
                ind_upper = ind.upper()

                if ind_upper == "RSI":
                    rsi = ta.rsi(df["close"], length=14)
                    if rsi is not None:
                        results["indicators"]["RSI"] = {
                            "value": round(float(rsi.iloc[-1]), 2),
                            "signal": _rsi_signal(float(rsi.iloc[-1])),
                        }

                elif ind_upper == "MACD":
                    macd = ta.macd(df["close"])
                    if macd is not None:
                        cols = macd.columns.tolist()
                        results["indicators"]["MACD"] = {
                            "macd": round(float(macd[cols[0]].iloc[-1]), 2),
                            "signal": round(float(macd[cols[1]].iloc[-1]), 2),
                            "histogram": round(float(macd[cols[2]].iloc[-1]), 2),
                        }

                elif ind_upper == "EMA":
                    ema20 = ta.ema(df["close"], length=20)
                    ema50 = ta.ema(df["close"], length=50)
                    results["indicators"]["EMA"] = {}
                    if ema20 is not None:
                        results["indicators"]["EMA"]["EMA_20"] = round(float(ema20.iloc[-1]), 2)
                    if ema50 is not None:
                        results["indicators"]["EMA"]["EMA_50"] = round(float(ema50.iloc[-1]), 2)

                elif ind_upper == "SMA":
                    sma20 = ta.sma(df["close"], length=20)
                    sma50 = ta.sma(df["close"], length=50)
                    results["indicators"]["SMA"] = {}
                    if sma20 is not None:
                        results["indicators"]["SMA"]["SMA_20"] = round(float(sma20.iloc[-1]), 2)
                    if sma50 is not None:
                        results["indicators"]["SMA"]["SMA_50"] = round(float(sma50.iloc[-1]), 2)

                elif ind_upper == "BBANDS":
                    bb = ta.bbands(df["close"], length=20)
                    if bb is not None:
                        cols = bb.columns.tolist()
                        results["indicators"]["BBANDS"] = {
                            "lower": round(float(bb[cols[0]].iloc[-1]), 2),
                            "mid": round(float(bb[cols[1]].iloc[-1]), 2),
                            "upper": round(float(bb[cols[2]].iloc[-1]), 2),
                        }

                elif ind_upper == "ADX":
                    adx = ta.adx(df["high"], df["low"], df["close"])
                    if adx is not None:
                        cols = adx.columns.tolist()
                        results["indicators"]["ADX"] = {
                            "value": round(float(adx[cols[0]].iloc[-1]), 2),
                            "signal": _adx_signal(float(adx[cols[0]].iloc[-1])),
                        }

                elif ind_upper == "VWAP":
                    vwap = ta.vwap(df["high"], df["low"], df["close"], df["volume"])
                    if vwap is not None:
                        results["indicators"]["VWAP"] = {
                            "value": round(float(vwap.iloc[-1]), 2),
                        }

                elif ind_upper == "STOCH":
                    stoch = ta.stoch(df["high"], df["low"], df["close"])
                    if stoch is not None:
                        cols = stoch.columns.tolist()
                        results["indicators"]["STOCH"] = {
                            "k": round(float(stoch[cols[0]].iloc[-1]), 2),
                            "d": round(float(stoch[cols[1]].iloc[-1]), 2),
                        }

                elif ind_upper == "ATR":
                    atr = ta.atr(df["high"], df["low"], df["close"])
                    if atr is not None:
                        results["indicators"]["ATR"] = {
                            "value": round(float(atr.iloc[-1]), 2),
                        }

                elif ind_upper == "OBV":
                    obv = ta.obv(df["close"], df["volume"])
                    if obv is not None:
                        results["indicators"]["OBV"] = {
                            "value": int(obv.iloc[-1]),
                        }

            return json.dumps(results, indent=2, default=str)
        except Exception as e:
            return f"Error computing indicators for {trading_symbol}: {e}"


def _rsi_signal(rsi: float) -> str:
    if rsi >= 70:
        return "OVERBOUGHT"
    elif rsi <= 30:
        return "OVERSOLD"
    return "NEUTRAL"


def _adx_signal(adx: float) -> str:
    if adx >= 25:
        return "STRONG_TREND"
    return "WEAK_TREND"

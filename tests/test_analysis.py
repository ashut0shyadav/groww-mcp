"""Tests for src/tools/analysis.py — technical indicator computations."""

import json
import time

import pytest
from mcp.server.fastmcp import FastMCP

from src.tools.analysis import register_analysis_tools


@pytest.fixture
def mcp_app():
    """Create an MCP app with analysis tools registered."""
    mcp = FastMCP("test")
    register_analysis_tools(mcp)
    return mcp


@pytest.fixture
def get_technical_indicators(mcp_app):
    """Extract the get_technical_indicators tool function."""
    return mcp_app._tool_manager._tools["get_technical_indicators"].fn


def _make_candles(count=60):
    """Generate synthetic OHLCV candle data."""
    base_ts = int(time.time()) - 86400 * 60
    return {
        "candles": [
            [
                base_ts + i * 86400,
                100 + i * 0.5,
                105 + i * 0.5,
                95 + i * 0.5,
                102 + i * 0.5,
                50000 + i * 1000,
            ]
            for i in range(count)
        ]
    }


@pytest.mark.asyncio
async def test_get_technical_indicators_rsi(patch_get_client, get_technical_indicators):
    """RSI indicator should return value between 0-100 and a signal."""
    patch_get_client.get_historical_candle_data.return_value = _make_candles(60)

    result = await get_technical_indicators("RELIANCE", ["RSI"])
    data = json.loads(result)

    assert "indicators" in data
    assert "RSI" in data["indicators"]
    rsi = data["indicators"]["RSI"]
    assert "value" in rsi
    assert 0 <= rsi["value"] <= 100
    assert rsi["signal"] in ("OVERBOUGHT", "OVERSOLD", "NEUTRAL")


@pytest.mark.asyncio
async def test_get_technical_indicators_macd(patch_get_client, get_technical_indicators):
    """MACD indicator should return macd, signal, and histogram values."""
    patch_get_client.get_historical_candle_data.return_value = _make_candles(60)

    result = await get_technical_indicators("RELIANCE", ["MACD"])
    data = json.loads(result)

    assert "indicators" in data
    assert "MACD" in data["indicators"]
    macd = data["indicators"]["MACD"]
    assert "macd" in macd
    assert "signal" in macd
    assert "histogram" in macd


@pytest.mark.asyncio
async def test_get_technical_indicators_multiple(patch_get_client, get_technical_indicators):
    """Multiple indicators requested should all be present in results."""
    patch_get_client.get_historical_candle_data.return_value = _make_candles(60)

    result = await get_technical_indicators("RELIANCE", ["RSI", "EMA", "SMA"])
    data = json.loads(result)

    assert "indicators" in data
    assert "RSI" in data["indicators"]
    assert "EMA" in data["indicators"]
    assert "SMA" in data["indicators"]


@pytest.mark.asyncio
async def test_get_technical_indicators_bbands(patch_get_client, get_technical_indicators):
    """Bollinger Bands should return lower, mid, and upper values."""
    patch_get_client.get_historical_candle_data.return_value = _make_candles(60)

    result = await get_technical_indicators("RELIANCE", ["BBANDS"])
    data = json.loads(result)

    assert "indicators" in data
    assert "BBANDS" in data["indicators"]
    bbands = data["indicators"]["BBANDS"]
    assert "lower" in bbands
    assert "mid" in bbands
    assert "upper" in bbands


@pytest.mark.asyncio
async def test_get_technical_indicators_no_candles(patch_get_client, get_technical_indicators):
    """Empty candle data should return an error."""
    patch_get_client.get_historical_candle_data.return_value = {"candles": []}

    result = await get_technical_indicators("RELIANCE", ["RSI"])
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
async def test_get_technical_indicators_error(patch_get_client, get_technical_indicators):
    """Exception during processing should return an error string."""
    patch_get_client.get_historical_candle_data.side_effect = Exception("API failure")

    result = await get_technical_indicators("RELIANCE", ["RSI"])

    assert "Error" in result

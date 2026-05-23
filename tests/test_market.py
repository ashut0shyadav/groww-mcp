"""Tests for market data MCP tools (src/tools/market.py)."""

import json

import pandas as pd
import pytest
from mcp.server.fastmcp import FastMCP

from src.tools import market as market_module
from src.tools.market import register_market_tools


@pytest.fixture(autouse=True)
def clear_instrument_cache():
    """Reset the instruments cache between tests."""
    market_module._instruments_cache["df"] = None
    yield
    market_module._instruments_cache["df"] = None


@pytest.fixture
def mcp_instance():
    """Create a FastMCP instance with market tools registered."""
    mcp = FastMCP("test")
    register_market_tools(mcp)
    return mcp


@pytest.fixture
def search_instrument_fn(mcp_instance):
    return mcp_instance._tool_manager._tools["search_instrument"].fn


@pytest.fixture
def get_quote_fn(mcp_instance):
    return mcp_instance._tool_manager._tools["get_quote"].fn


@pytest.fixture
def get_ltp_fn(mcp_instance):
    return mcp_instance._tool_manager._tools["get_ltp"].fn


@pytest.fixture
def get_ohlc_fn(mcp_instance):
    return mcp_instance._tool_manager._tools["get_ohlc"].fn


@pytest.fixture
def get_historical_candles_fn(mcp_instance):
    return mcp_instance._tool_manager._tools["get_historical_candles"].fn


@pytest.fixture
def get_option_chain_fn(mcp_instance):
    return mcp_instance._tool_manager._tools["get_option_chain"].fn


@pytest.mark.asyncio
async def test_search_instrument(patch_get_client, search_instrument_fn):
    """Test that searching for 'reliance' returns matching instruments."""
    mock_client = patch_get_client

    df = pd.DataFrame([
        {"exchange": "NSE", "trading_symbol": "RELIANCE", "name": "Reliance Industries Ltd", "segment": "CASH", "instrument_type": "EQ"},
        {"exchange": "NSE", "trading_symbol": "INFY", "name": "Infosys Ltd", "segment": "CASH", "instrument_type": "EQ"},
        {"exchange": "NSE", "trading_symbol": "TCS", "name": "Tata Consultancy Services", "segment": "CASH", "instrument_type": "EQ"},
    ])
    mock_client.get_all_instruments.return_value = df

    result = await search_instrument_fn(query="reliance")
    parsed = json.loads(result)

    assert len(parsed) > 0
    symbols = [r["trading_symbol"] for r in parsed]
    assert "RELIANCE" in symbols


@pytest.mark.asyncio
async def test_search_instrument_limit(patch_get_client, search_instrument_fn):
    """Test that search results are limited to 10."""
    mock_client = patch_get_client

    # Create 15 rows that all match the query
    rows = [
        {"exchange": "NSE", "trading_symbol": f"TEST{i}", "name": f"Test Company {i}", "segment": "CASH", "instrument_type": "EQ"}
        for i in range(15)
    ]
    df = pd.DataFrame(rows)
    mock_client.get_all_instruments.return_value = df

    result = await search_instrument_fn(query="test")
    parsed = json.loads(result)

    assert len(parsed) == 10


@pytest.mark.asyncio
async def test_search_instrument_no_results(patch_get_client, search_instrument_fn):
    """Test that searching for a non-existent symbol returns empty list."""
    mock_client = patch_get_client

    df = pd.DataFrame([
        {"exchange": "NSE", "trading_symbol": "RELIANCE", "name": "Reliance Industries Ltd", "segment": "CASH", "instrument_type": "EQ"},
        {"exchange": "NSE", "trading_symbol": "INFY", "name": "Infosys Ltd", "segment": "CASH", "instrument_type": "EQ"},
    ])
    mock_client.get_all_instruments.return_value = df

    result = await search_instrument_fn(query="ZZZZZ")
    parsed = json.loads(result)

    assert parsed == []


@pytest.mark.asyncio
async def test_get_quote(patch_get_client, get_quote_fn):
    """Test get_quote returns correct last_price."""
    mock_client = patch_get_client
    mock_client.get_quote.return_value = {"last_price": 2500.5, "volume": 1000000}

    result = await get_quote_fn(trading_symbol="RELIANCE")
    parsed = json.loads(result)

    assert parsed["last_price"] == 2500.5
    assert parsed["volume"] == 1000000


@pytest.mark.asyncio
async def test_get_ltp(patch_get_client, get_ltp_fn):
    """Test get_ltp returns prices for multiple symbols."""
    mock_client = patch_get_client
    mock_client.get_ltp.return_value = {"NSE_RELIANCE": 2500.5, "NSE_INFY": 1800.0}

    result = await get_ltp_fn(symbols=["RELIANCE", "INFY"])
    parsed = json.loads(result)

    assert parsed["NSE_RELIANCE"] == 2500.5
    assert parsed["NSE_INFY"] == 1800.0


@pytest.mark.asyncio
async def test_get_ohlc(patch_get_client, get_ohlc_fn):
    """Test get_ohlc returns correct OHLC values."""
    mock_client = patch_get_client
    mock_client.get_ohlc.return_value = {
        "NSE_RELIANCE": {"open": 2490, "high": 2510, "low": 2480, "close": 2500}
    }

    result = await get_ohlc_fn(symbols=["RELIANCE"])
    parsed = json.loads(result)

    assert parsed["NSE_RELIANCE"]["open"] == 2490
    assert parsed["NSE_RELIANCE"]["high"] == 2510
    assert parsed["NSE_RELIANCE"]["low"] == 2480
    assert parsed["NSE_RELIANCE"]["close"] == 2500


@pytest.mark.asyncio
async def test_get_historical_candles(patch_get_client, get_historical_candles_fn):
    """Test get_historical_candles returns formatted candle data."""
    mock_client = patch_get_client
    mock_client.get_historical_candle_data.return_value = {
        "candles": [
            [1700000000, 100, 105, 95, 102, 50000],
            [1700086400, 102, 108, 100, 106, 60000],
        ]
    }

    result = await get_historical_candles_fn(trading_symbol="RELIANCE")
    parsed = json.loads(result)

    assert parsed["candle_count"] == 2
    assert len(parsed["candles"]) == 2

    candle = parsed["candles"][0]
    assert candle["timestamp"] == 1700000000
    assert candle["open"] == 100
    assert candle["high"] == 105
    assert candle["low"] == 95
    assert candle["close"] == 102
    assert candle["volume"] == 50000


@pytest.mark.asyncio
async def test_get_option_chain(patch_get_client, get_option_chain_fn):
    """Test get_option_chain returns underlying LTP and strike data."""
    mock_client = patch_get_client
    mock_client.get_option_chain.return_value = {
        "underlying_ltp": 22500,
        "strikes": {
            "22500": {
                "CE": {"ltp": 150},
                "PE": {"ltp": 120},
            }
        },
    }

    result = await get_option_chain_fn(underlying="NIFTY", expiry_date="2025-11-28")
    parsed = json.loads(result)

    assert parsed["underlying_ltp"] == 22500
    assert parsed["strikes"]["22500"]["CE"]["ltp"] == 150
    assert parsed["strikes"]["22500"]["PE"]["ltp"] == 120


@pytest.mark.asyncio
async def test_get_quote_error(patch_get_client, get_quote_fn):
    """Test get_quote handles API errors gracefully."""
    mock_client = patch_get_client
    mock_client.get_quote.side_effect = Exception("API timeout")

    result = await get_quote_fn(trading_symbol="RELIANCE")

    assert "Error" in result
    assert "API timeout" in result

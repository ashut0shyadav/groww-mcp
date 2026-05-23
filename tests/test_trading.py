"""Tests for the trading MCP tools (place_order, modify_order, cancel_order)."""

import json
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from src.tools.trading import register_trading_tools


@pytest.fixture
def trading_tools(patch_get_client):
    """Register trading tools on a test MCP server and return tool functions."""
    mcp = FastMCP("test")
    register_trading_tools(mcp)
    return {
        "place_order": mcp._tool_manager._tools["place_order"].fn,
        "modify_order": mcp._tool_manager._tools["modify_order"].fn,
        "cancel_order": mcp._tool_manager._tools["cancel_order"].fn,
    }


@pytest.mark.asyncio
async def test_place_order_paper_mode(trading_tools, mock_groww_client):
    """Paper mode returns SIMULATED status without calling the real API."""
    with patch("src.tools.trading.guard.is_paper_mode", return_value=True), \
         patch("src.tools.trading.guard.validate_order", return_value=(True, "")):
        result = await trading_tools["place_order"]("RELIANCE", 1, "BUY")

    data = json.loads(result)
    assert data["mode"] == "PAPER"
    assert data["status"] == "SIMULATED"
    mock_groww_client.place_order.assert_not_called()


@pytest.mark.asyncio
async def test_place_order_real(trading_tools, mock_groww_client):
    """Real mode calls groww.place_order and records the order value."""
    mock_groww_client.place_order.return_value = {
        "groww_order_id": "GMK123",
        "order_status": "OPEN",
        "remark": "Order placed",
    }

    with patch("src.tools.trading.guard.is_paper_mode", return_value=False), \
         patch("src.tools.trading.guard.validate_order", return_value=(True, "")), \
         patch("src.tools.trading.guard.record_order") as mock_record:
        result = await trading_tools["place_order"](
            "WIPRO", 5, "BUY", order_type="LIMIT", price=250
        )

    data = json.loads(result)
    assert data["groww_order_id"] == "GMK123"
    mock_record.assert_called_once_with(5 * 250)


@pytest.mark.asyncio
async def test_place_order_blocked_by_safety(trading_tools):
    """Order blocked by safety guard returns an error with the reason."""
    with patch(
        "src.tools.trading.guard.validate_order",
        return_value=(False, "Order value ₹50000 exceeds limit ₹10000"),
    ):
        result = await trading_tools["place_order"]("RELIANCE", 100, "BUY", price=500)

    data = json.loads(result)
    assert "error" in data
    assert "exceeds limit" in data["error"]


@pytest.mark.asyncio
async def test_place_order_fno_blocked(trading_tools):
    """F&O trading disabled by safety guard returns an error."""
    with patch(
        "src.tools.trading.guard.validate_order",
        return_value=(False, "F&O trading is disabled"),
    ):
        result = await trading_tools["place_order"](
            "NIFTY", 50, "BUY", segment="FNO"
        )

    data = json.loads(result)
    assert "error" in data
    assert "F&O trading is disabled" in data["error"]


@pytest.mark.asyncio
async def test_modify_order(trading_tools, mock_groww_client):
    """modify_order calls groww.modify_order and returns the response."""
    mock_groww_client.modify_order.return_value = {
        "groww_order_id": "GMK123",
        "order_status": "OPEN",
    }

    result = await trading_tools["modify_order"]("GMK123", 10)

    data = json.loads(result)
    assert data["groww_order_id"] == "GMK123"
    assert data["order_status"] == "OPEN"


@pytest.mark.asyncio
async def test_cancel_order(trading_tools, mock_groww_client):
    """cancel_order calls groww.cancel_order and returns CANCELLED status."""
    mock_groww_client.cancel_order.return_value = {
        "groww_order_id": "GMK123",
        "order_status": "CANCELLED",
    }

    result = await trading_tools["cancel_order"]("GMK123")

    data = json.loads(result)
    assert data["groww_order_id"] == "GMK123"
    assert data["order_status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_place_order_exception(trading_tools, mock_groww_client):
    """Exception during place_order is caught and returned as an error."""
    mock_groww_client.place_order.side_effect = Exception("Network error")

    with patch("src.tools.trading.guard.is_paper_mode", return_value=False), \
         patch("src.tools.trading.guard.validate_order", return_value=(True, "")):
        result = await trading_tools["place_order"]("INFY", 2, "BUY")

    data = json.loads(result)
    assert "error" in data
    assert "Network error" in data["error"]

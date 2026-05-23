"""Tests for src/tools/portfolio.py portfolio tools."""

import json

import pytest
from mcp.server.fastmcp import FastMCP

from src.tools.portfolio import register_portfolio_tools


@pytest.fixture
def portfolio_tools(patch_get_client):
    """Register portfolio tools on a fresh MCP instance and return tool functions."""
    mcp = FastMCP("test")
    register_portfolio_tools(mcp)
    tools = mcp._tool_manager._tools
    return tools


@pytest.fixture
def groww(patch_get_client):
    """Return the mock groww client for setting up return values."""
    return patch_get_client


class TestGetHoldings:

    @pytest.mark.asyncio
    async def test_get_holdings(self, portfolio_tools, groww):
        """Should return a JSON list of holdings."""
        groww.get_holdings_for_user.return_value = [
            {
                "isin": "INE002A01018",
                "trading_symbol": "RELIANCE",
                "quantity": 10,
                "average_price": 2400,
            }
        ]

        get_holdings = portfolio_tools["get_holdings"].fn
        result = await get_holdings()
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["trading_symbol"] == "RELIANCE"
        assert parsed[0]["quantity"] == 10
        groww.get_holdings_for_user.assert_called_once_with(timeout=5)

    @pytest.mark.asyncio
    async def test_get_holdings_empty(self, portfolio_tools, groww):
        """Should return an empty list when no holdings exist."""
        groww.get_holdings_for_user.return_value = []

        get_holdings = portfolio_tools["get_holdings"].fn
        result = await get_holdings()
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 0

    @pytest.mark.asyncio
    async def test_get_holdings_error(self, portfolio_tools, groww):
        """Should return an error message when the API call fails."""
        groww.get_holdings_for_user.side_effect = Exception("Timeout")

        get_holdings = portfolio_tools["get_holdings"].fn
        result = await get_holdings()

        assert "Error" in result
        assert "Timeout" in result


class TestGetPositions:

    @pytest.mark.asyncio
    async def test_get_positions(self, portfolio_tools, groww):
        """Should return a JSON list of positions."""
        groww.get_positions_for_user.return_value = [
            {
                "trading_symbol": "INFY",
                "segment": "CASH",
                "quantity": 5,
                "realised_pnl": 200,
            }
        ]

        get_positions = portfolio_tools["get_positions"].fn
        result = await get_positions(segment="")
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["trading_symbol"] == "INFY"
        assert parsed[0]["realised_pnl"] == 200
        groww.get_positions_for_user.assert_called_once_with(segment=None)

    @pytest.mark.asyncio
    async def test_get_positions_filtered(self, portfolio_tools, groww):
        """Should pass the segment filter to the API."""
        groww.get_positions_for_user.return_value = [
            {
                "trading_symbol": "INFY",
                "segment": "CASH",
                "quantity": 5,
                "realised_pnl": 200,
            }
        ]

        get_positions = portfolio_tools["get_positions"].fn
        result = await get_positions(segment="CASH")
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 1
        groww.get_positions_for_user.assert_called_once_with(segment="CASH")


class TestGetOrders:

    @pytest.mark.asyncio
    async def test_get_orders(self, portfolio_tools, groww):
        """Should return a JSON object with order_list."""
        groww.get_order_list.return_value = {
            "order_list": [
                {
                    "groww_order_id": "GMK1",
                    "trading_symbol": "TCS",
                    "order_status": "EXECUTED",
                }
            ]
        }

        get_orders = portfolio_tools["get_orders"].fn
        result = await get_orders(segment="", page=0)
        parsed = json.loads(result)

        assert "order_list" in parsed
        assert len(parsed["order_list"]) == 1
        assert parsed["order_list"][0]["groww_order_id"] == "GMK1"
        assert parsed["order_list"][0]["order_status"] == "EXECUTED"
        groww.get_order_list.assert_called_once_with(
            segment=None, page=0, page_size=25
        )


class TestGetOrderStatus:

    @pytest.mark.asyncio
    async def test_get_order_status(self, portfolio_tools, groww):
        """Should return order status details for a specific order."""
        groww.get_order_status.return_value = {
            "groww_order_id": "GMK1",
            "order_status": "EXECUTED",
            "filled_quantity": 10,
        }

        get_order_status = portfolio_tools["get_order_status"].fn
        result = await get_order_status(groww_order_id="GMK1", segment="CASH")
        parsed = json.loads(result)

        assert parsed["groww_order_id"] == "GMK1"
        assert parsed["order_status"] == "EXECUTED"
        assert parsed["filled_quantity"] == 10
        groww.get_order_status.assert_called_once_with(
            groww_order_id="GMK1", segment="CASH"
        )

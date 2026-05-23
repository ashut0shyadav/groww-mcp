import json

from mcp.server.fastmcp import FastMCP

from src.auth import get_client
from src.paper_engine import engine
from src.safety import guard


def _map_segment(segment: str):
    """Map a segment string to the corresponding groww constant."""
    groww = get_client()
    segment_upper = segment.strip().upper()
    if segment_upper == "CASH":
        return groww.SEGMENT_CASH
    elif segment_upper == "FNO":
        return groww.SEGMENT_FNO
    return None


def register_portfolio_tools(mcp: FastMCP):

    @mcp.tool()
    async def get_holdings() -> str:
        """Get all stock holdings in the user's demat account.

        In paper mode, returns virtual holdings from the paper trading portfolio.

        Returns a JSON list of holdings with details like trading symbol,
        quantity, and average price.
        """
        try:
            if guard.is_paper_mode():
                holdings = engine.get_holdings()
                return json.dumps(holdings, indent=2)

            groww = get_client()
            holdings = groww.get_holdings_for_user(timeout=5)
            return json.dumps(holdings, indent=2)
        except Exception as e:
            return f"Error fetching holdings: {e}"

    @mcp.tool()
    async def get_positions(segment: str = "") -> str:
        """Get current trading positions for the user.

        In paper mode, returns virtual positions from the paper trading portfolio.

        Args:
            segment: Filter by segment - "CASH" for equity, "FNO" for futures
                     and options, or empty string for all positions.

        Returns a JSON list of positions with details like trading symbol,
        segment, exchange, quantity, product, net price, and realised P&L.
        """
        try:
            if guard.is_paper_mode():
                positions = engine.get_positions()
                return json.dumps(positions, indent=2)

            groww = get_client()
            seg = _map_segment(segment) if segment else None
            positions = groww.get_positions_for_user(segment=seg)
            return json.dumps(positions, indent=2)
        except Exception as e:
            return f"Error fetching positions: {e}"

    @mcp.tool()
    async def get_orders(segment: str = "", page: int = 0) -> str:
        """Get the list of today's orders placed by the user.

        In paper mode, returns paper order history.

        Args:
            segment: Filter by segment - "CASH" for equity, "FNO" for futures
                     and options, or empty string for all orders.
            page: Page number for pagination (0-indexed). Each page has 25 orders.

        Returns a JSON object with order_list containing order details.
        """
        try:
            if guard.is_paper_mode():
                from datetime import datetime
                from zoneinfo import ZoneInfo
                today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                orders = engine.get_orders(date=today)
                return json.dumps(orders, indent=2, default=str)

            groww = get_client()
            seg = _map_segment(segment) if segment else None
            orders = groww.get_order_list(segment=seg, page=page, page_size=25)
            return json.dumps(orders, indent=2)
        except Exception as e:
            return f"Error fetching orders: {e}"

    @mcp.tool()
    async def get_order_status(groww_order_id: str, segment: str = "CASH") -> str:
        """Get the status of a specific order by its order ID.

        In paper mode, looks up paper order by ID.

        Args:
            groww_order_id: The unique order identifier.
            segment: The segment of the order - "CASH" (default) or "FNO".

        Returns a JSON object with order status details.
        """
        try:
            if guard.is_paper_mode():
                status = engine.get_order_status(groww_order_id)
                return json.dumps(status, indent=2, default=str)

            groww = get_client()
            seg = _map_segment(segment)
            if seg is None:
                seg = groww.SEGMENT_CASH
            status = groww.get_order_status(
                groww_order_id=groww_order_id, segment=seg
            )
            return json.dumps(status, indent=2)
        except Exception as e:
            return f"Error fetching order status: {e}"

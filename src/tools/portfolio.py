import json

from mcp.server.fastmcp import FastMCP

from src.auth import get_client


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

        Returns a JSON list of holdings with details like ISIN, trading symbol,
        quantity, average price, pledge quantity, and demat free quantity.
        """
        try:
            groww = get_client()
            holdings = groww.get_holdings_for_user(timeout=5)
            return json.dumps(holdings, indent=2)
        except Exception as e:
            return f"Error fetching holdings: {e}"

    @mcp.tool()
    async def get_positions(segment: str = "") -> str:
        """Get current trading positions for the user.

        Args:
            segment: Filter by segment - "CASH" for equity, "FNO" for futures
                     and options, or empty string for all positions.

        Returns a JSON list of positions with details like trading symbol,
        segment, exchange, quantity, product, net price, and realised P&L.
        """
        try:
            groww = get_client()
            seg = _map_segment(segment) if segment else None
            positions = groww.get_positions_for_user(segment=seg)
            return json.dumps(positions, indent=2)
        except Exception as e:
            return f"Error fetching positions: {e}"

    @mcp.tool()
    async def get_orders(segment: str = "", page: int = 0) -> str:
        """Get the list of today's orders placed by the user.

        Args:
            segment: Filter by segment - "CASH" for equity, "FNO" for futures
                     and options, or empty string for all orders.
            page: Page number for pagination (0-indexed). Each page has 25 orders.

        Returns a JSON object with order_list containing order details like
        groww_order_id, trading symbol, status, quantity, price, and timestamps.
        """
        try:
            groww = get_client()
            seg = _map_segment(segment) if segment else None
            orders = groww.get_order_list(segment=seg, page=page, page_size=25)
            return json.dumps(orders, indent=2)
        except Exception as e:
            return f"Error fetching orders: {e}"

    @mcp.tool()
    async def get_order_status(groww_order_id: str, segment: str = "CASH") -> str:
        """Get the status of a specific order by its Groww order ID.

        Args:
            groww_order_id: The unique order identifier from Groww.
            segment: The segment of the order - "CASH" (default) or "FNO".

        Returns a JSON object with order status details including order status,
        remark, filled quantity, and order reference ID.
        """
        try:
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

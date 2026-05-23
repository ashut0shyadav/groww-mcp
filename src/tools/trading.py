"""MCP tools for placing, modifying, and canceling orders via the Groww API."""

import json

from mcp.server.fastmcp import FastMCP

from src.auth import get_client
from src.safety import guard


def _map_exchange(groww, exchange: str):
    """Map exchange string to SDK constant."""
    return {"NSE": groww.EXCHANGE_NSE, "BSE": groww.EXCHANGE_BSE}.get(
        exchange, groww.EXCHANGE_NSE
    )


def _map_segment(groww, segment: str):
    """Map segment string to SDK constant."""
    return {"CASH": groww.SEGMENT_CASH, "FNO": groww.SEGMENT_FNO}.get(
        segment, groww.SEGMENT_CASH
    )


def _map_product(groww, product: str):
    """Map product string to SDK constant."""
    return {"CNC": groww.PRODUCT_CNC}.get(product, groww.PRODUCT_CNC)


def _map_order_type(groww, order_type: str):
    """Map order type string to SDK constant."""
    return {
        "LIMIT": groww.ORDER_TYPE_LIMIT,
        "MARKET": groww.ORDER_TYPE_MARKET,
        "STOP_LOSS": groww.ORDER_TYPE_STOP_LOSS,
        "STOP_LOSS_MARKET": groww.ORDER_TYPE_STOP_LOSS_MARKET,
    }.get(order_type, groww.ORDER_TYPE_MARKET)


def _map_transaction_type(groww, transaction_type: str):
    """Map transaction type string to SDK constant."""
    return {
        "BUY": groww.TRANSACTION_TYPE_BUY,
        "SELL": groww.TRANSACTION_TYPE_SELL,
    }.get(transaction_type, groww.TRANSACTION_TYPE_BUY)


def _estimate_price(trading_symbol: str, price: float, exchange: str) -> float:
    """For MARKET orders (price=0), fetch LTP to estimate order value."""
    if price > 0:
        return price
    try:
        groww = get_client()
        symbol_key = f"{exchange.upper()}_{trading_symbol.upper()}"
        ltp_data = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols=symbol_key,
        )
        return float(ltp_data.get(symbol_key, 0))
    except Exception:
        return 0


def register_trading_tools(mcp: FastMCP):
    """Register all trading-related MCP tools on the given server."""

    @mcp.tool()
    async def place_order(
        trading_symbol: str,
        quantity: int,
        transaction_type: str,
        order_type: str = "MARKET",
        price: float = 0,
        trigger_price: float = 0,
        exchange: str = "NSE",
        segment: str = "CASH",
        product: str = "CNC",
    ) -> str:
        """Place a buy or sell order on the Groww platform.

        Args:
            trading_symbol: The stock/instrument symbol (e.g., "WIPRO").
            quantity: Number of shares/lots to trade.
            transaction_type: "BUY" or "SELL".
            order_type: "MARKET", "LIMIT", "STOP_LOSS", or "STOP_LOSS_MARKET".
            price: Limit price (required for LIMIT/STOP_LOSS orders).
            trigger_price: Trigger price for stop-loss orders.
            exchange: "NSE" or "BSE".
            segment: "CASH" or "FNO".
            product: "CNC" (Cash and Carry).

        Returns:
            JSON string with order details or error message.
        """
        try:
            estimated_price = _estimate_price(trading_symbol, price, exchange)
            allowed, message = guard.validate_order(
                trading_symbol, quantity, estimated_price, segment, transaction_type
            )
            if not allowed:
                return json.dumps({"error": message})

            if guard.is_paper_mode():
                return json.dumps(
                    {
                        "mode": "PAPER",
                        "trading_symbol": trading_symbol,
                        "quantity": quantity,
                        "estimated_price": estimated_price,
                        "order_type": order_type,
                        "transaction_type": transaction_type,
                        "status": "SIMULATED",
                    }
                )

            groww = get_client()
            response = groww.place_order(
                trading_symbol=trading_symbol,
                quantity=quantity,
                validity=groww.VALIDITY_DAY,
                exchange=_map_exchange(groww, exchange),
                segment=_map_segment(groww, segment),
                product=_map_product(groww, product),
                order_type=_map_order_type(groww, order_type),
                transaction_type=_map_transaction_type(groww, transaction_type),
                price=price,
                trigger_price=trigger_price,
            )
            guard.record_order(quantity * estimated_price)
            return json.dumps(response)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def modify_order(
        groww_order_id: str,
        quantity: int,
        order_type: str = "MARKET",
        price: float = 0,
        trigger_price: float = 0,
        segment: str = "CASH",
    ) -> str:
        """Modify an existing open order.

        Args:
            groww_order_id: The unique order ID returned by place_order.
            quantity: New quantity for the order.
            order_type: "MARKET", "LIMIT", "STOP_LOSS", or "STOP_LOSS_MARKET".
            price: New limit price (if applicable).
            trigger_price: New trigger price (if applicable).
            segment: "CASH" or "FNO".

        Returns:
            JSON string with modified order details or error message.
        """
        try:
            groww = get_client()
            response = groww.modify_order(
                quantity=quantity,
                order_type=_map_order_type(groww, order_type),
                segment=_map_segment(groww, segment),
                groww_order_id=groww_order_id,
                price=price,
                trigger_price=trigger_price,
            )
            return json.dumps(response)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def cancel_order(
        groww_order_id: str,
        segment: str = "CASH",
    ) -> str:
        """Cancel an existing open order.

        Args:
            groww_order_id: The unique order ID to cancel.
            segment: "CASH" or "FNO".

        Returns:
            JSON string with cancellation details or error message.
        """
        try:
            groww = get_client()
            response = groww.cancel_order(
                segment=_map_segment(groww, segment),
                groww_order_id=groww_order_id,
            )
            return json.dumps(response)
        except Exception as e:
            return json.dumps({"error": str(e)})

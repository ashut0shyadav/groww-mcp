"""MCP tools for placing, modifying, and canceling orders via the Groww API."""

import json

from mcp.server.fastmcp import FastMCP

from src.auth import get_client
from src.evaluation import evaluator
from src.paper_engine import engine
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
    return {
        "CNC": groww.PRODUCT_CNC,
        "MIS": groww.PRODUCT_MIS,
        "NRML": groww.PRODUCT_NRML,
    }.get(product, groww.PRODUCT_CNC)


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
        amo: bool = False,
        strategy: str = "",
        indicators: str = "",
    ) -> str:
        """Place a buy or sell order on the Groww platform.

        In paper mode, the order executes against a virtual portfolio with
        real market prices. Tag your trades with a strategy name for
        performance tracking.

        Args:
            trading_symbol: The stock/instrument symbol (e.g., "WIPRO").
            quantity: Number of shares/lots to trade.
            transaction_type: "BUY" or "SELL".
            order_type: "MARKET", "LIMIT", "STOP_LOSS", or "STOP_LOSS_MARKET".
            price: Limit price (required for LIMIT/STOP_LOSS orders).
            trigger_price: Trigger price for stop-loss orders.
            exchange: "NSE" or "BSE".
            segment: "CASH" or "FNO".
            product: "CNC" (Cash and Carry), "MIS" (Intraday), or "NRML" (Normal).
            amo: Set to true to place an After Market Order.
            strategy: Strategy name for evaluation tracking (e.g., "RSI_OVERSOLD", "MACD_CROSSOVER").
            indicators: JSON string of indicator values at time of trade (e.g., '{"RSI": 28.5}').

        Returns:
            JSON string with order details or error message.
        """
        try:
            estimated_price = _estimate_price(trading_symbol, price, exchange)
            allowed, message = guard.validate_order(
                trading_symbol, quantity, estimated_price, segment, transaction_type, amo=amo
            )
            if not allowed:
                return json.dumps({"error": message})

            if guard.is_paper_mode():
                indicators_dict = {}
                if indicators:
                    try:
                        indicators_dict = json.loads(indicators)
                    except json.JSONDecodeError:
                        pass

                result = engine.execute_order(
                    symbol=trading_symbol.upper(),
                    quantity=quantity,
                    transaction_type=transaction_type.upper(),
                    order_type=order_type.upper(),
                    price=price,
                    exchange=exchange.upper(),
                    strategy=strategy,
                    indicators=indicators_dict,
                )

                if "error" not in result:
                    evaluator.log_trade({
                        "paper_order_id": result.get("paper_order_id"),
                        "symbol": trading_symbol.upper(),
                        "action": transaction_type.upper(),
                        "quantity": quantity,
                        "fill_price": result.get("fill_price", 0),
                        "strategy": strategy,
                        "indicators": indicators_dict,
                        "timestamp": result.get("timestamp", ""),
                    })

                return json.dumps(result, indent=2, default=str)

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
            if guard.is_paper_mode():
                return json.dumps({"error": "Paper orders execute immediately and cannot be modified"})

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
            if guard.is_paper_mode():
                result = engine.cancel_order(groww_order_id)
                return json.dumps(result)

            groww = get_client()
            response = groww.cancel_order(
                segment=_map_segment(groww, segment),
                groww_order_id=groww_order_id,
            )
            return json.dumps(response)
        except Exception as e:
            return json.dumps({"error": str(e)})

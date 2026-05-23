import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from src.auth import get_client

IST = ZoneInfo("Asia/Kolkata")


class PaperEngine:
    def __init__(self, data_dir: Path, starting_balance: int):
        self.data_dir = data_dir
        self.starting_balance = starting_balance
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.portfolio_path = self.data_dir / "portfolio.json"
        self.orders_path = self.data_dir / "orders.json"
        self.portfolio = self._load_portfolio()
        self.orders = self._load_orders()

    # ─── Persistence helpers ───────────────────────────────────────────

    def _load_portfolio(self) -> dict:
        if self.portfolio_path.exists():
            with open(self.portfolio_path, "r") as f:
                return json.load(f)
        return {
            "balance": self.starting_balance,
            "positions": {},
            "total_realized_pnl": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
        }

    def _save_portfolio(self) -> None:
        with open(self.portfolio_path, "w") as f:
            json.dump(self.portfolio, f, indent=2)

    def _load_orders(self) -> list:
        if self.orders_path.exists():
            with open(self.orders_path, "r") as f:
                return json.load(f)
        return []

    def _save_orders(self) -> None:
        with open(self.orders_path, "w") as f:
            json.dump(self.orders, f, indent=2)

    # ─── Core trading ──────────────────────────────────────────────────

    def execute_order(
        self,
        symbol: str,
        quantity: int,
        transaction_type: str,
        order_type: str,
        price: float,
        exchange: str,
        strategy: str = "",
        indicators: dict | None = None,
    ) -> dict:
        timestamp = datetime.now(IST).isoformat()

        # Determine fill price
        if order_type.upper() == "MARKET":
            groww = get_client()
            ltp_data = groww.get_ltp(
                segment=groww.SEGMENT_CASH,
                exchange_trading_symbols=f"{exchange}_{symbol}",
            )
            fill_price = float(ltp_data)
        else:
            fill_price = float(price)

        order_value = fill_price * quantity
        positions = self.portfolio["positions"]

        # BUY logic
        if transaction_type.upper() == "BUY":
            if self.portfolio["balance"] < order_value:
                return {
                    "status": "REJECTED",
                    "reason": "Insufficient balance",
                    "available_balance": self.portfolio["balance"],
                    "required": order_value,
                }
            self.portfolio["balance"] -= order_value

            if symbol in positions:
                existing = positions[symbol]
                new_qty = existing["quantity"] + quantity
                new_invested = existing["invested"] + order_value
                positions[symbol] = {
                    "quantity": new_qty,
                    "avg_price": new_invested / new_qty,
                    "invested": new_invested,
                }
            else:
                positions[symbol] = {
                    "quantity": quantity,
                    "avg_price": fill_price,
                    "invested": order_value,
                }

        # SELL logic
        elif transaction_type.upper() == "SELL":
            if symbol not in positions or positions[symbol]["quantity"] < quantity:
                return {
                    "status": "REJECTED",
                    "reason": "Insufficient quantity to sell",
                    "available_quantity": positions.get(symbol, {}).get("quantity", 0),
                    "requested": quantity,
                }

            position = positions[symbol]
            pnl = (fill_price - position["avg_price"]) * quantity
            self.portfolio["total_realized_pnl"] += pnl
            self.portfolio["balance"] += order_value

            if pnl > 0:
                self.portfolio["winning_trades"] += 1
            else:
                self.portfolio["losing_trades"] += 1

            position["quantity"] -= quantity
            position["invested"] -= position["avg_price"] * quantity
            if position["quantity"] == 0:
                del positions[symbol]
            else:
                positions[symbol] = position

        # Update stats
        self.portfolio["total_trades"] += 1

        # Generate order ID
        paper_order_id = f"PAPER_{len(self.orders) + 1:04d}"

        # Build order record
        order_record = {
            "paper_order_id": paper_order_id,
            "trading_symbol": symbol,
            "exchange": exchange,
            "segment": "CASH",
            "transaction_type": transaction_type.upper(),
            "order_type": order_type.upper(),
            "quantity": quantity,
            "fill_price": fill_price,
            "order_value": order_value,
            "status": "EXECUTED",
            "strategy": strategy,
            "indicators": indicators or {},
            "timestamp": timestamp,
            "product": "CNC",
        }

        self.orders.append(order_record)
        self._save_orders()
        self._save_portfolio()

        return {
            "paper_order_id": paper_order_id,
            "trading_symbol": symbol,
            "fill_price": fill_price,
            "order_value": order_value,
            "status": "EXECUTED",
            "strategy": strategy,
            "timestamp": timestamp,
        }

    # ─── Query methods ─────────────────────────────────────────────────

    def get_portfolio(self) -> dict:
        return {
            "balance": self.portfolio["balance"],
            "positions": self.portfolio["positions"],
            "total_realized_pnl": self.portfolio["total_realized_pnl"],
            "total_trades": self.portfolio["total_trades"],
            "winning_trades": self.portfolio["winning_trades"],
            "losing_trades": self.portfolio["losing_trades"],
        }

    def get_holdings(self) -> list:
        holdings = []
        for symbol, pos in self.portfolio["positions"].items():
            holdings.append({
                "trading_symbol": symbol,
                "quantity": pos["quantity"],
                "average_price": pos["avg_price"],
                "isin": "PAPER",
            })
        return holdings

    def get_positions(self) -> list:
        positions = []
        for symbol, pos in self.portfolio["positions"].items():
            positions.append({
                "trading_symbol": symbol,
                "segment": "CASH",
                "quantity": pos["quantity"],
                "net_price": pos["avg_price"],
                "exchange": "NSE",
                "product": "CNC",
            })
        return positions

    def get_orders(self, date: str = None) -> dict:
        if date:
            filtered = [
                o for o in self.orders
                if o["timestamp"].startswith(date)
            ]
            return {"order_list": filtered}
        return {"order_list": self.orders}

    def get_order_status(self, paper_order_id: str) -> dict:
        for order in self.orders:
            if order["paper_order_id"] == paper_order_id:
                return order
        return {"status": "NOT_FOUND", "paper_order_id": paper_order_id}

    def cancel_order(self, paper_order_id: str) -> dict:
        for order in self.orders:
            if order["paper_order_id"] == paper_order_id:
                if order["status"] == "PENDING":
                    order["status"] = "CANCELLED"
                    self._save_orders()
                    return {"paper_order_id": paper_order_id, "status": "CANCELLED"}
                return {
                    "paper_order_id": paper_order_id,
                    "status": order["status"],
                    "message": "Order already executed",
                }
        return {"status": "NOT_FOUND", "paper_order_id": paper_order_id}


# ─── Module-level singleton ───────────────────────────────────────────────

from src.config import DATA_DIR, PAPER_STARTING_BALANCE

engine = PaperEngine(DATA_DIR, PAPER_STARTING_BALANCE)

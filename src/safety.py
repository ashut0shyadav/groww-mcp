"""Order safety validation for the Groww MCP server.

Validates orders before they reach the Groww API, protecting against
accidental large trades and enforcing trading rules.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.config import ALLOW_FNO, MAX_DAILY_SPEND, MAX_ORDER_VALUE, PAPER_TRADING

IST = ZoneInfo("Asia/Kolkata")


class SafetyGuard:
    def __init__(self) -> None:
        self._daily_spend: dict[str, float] = {}

    def validate_order(
        self,
        trading_symbol: str,
        quantity: int,
        price: float,
        segment: str,
        transaction_type: str,
    ) -> tuple[bool, str]:
        """Validate an order against safety rules.

        Returns (True, "") if the order is allowed, or (False, reason) if blocked.
        """
        # Check F&O permission
        if segment == "FNO" and not ALLOW_FNO:
            return False, "F&O trading is disabled"

        # Check order value limit
        value = quantity * price
        if value > MAX_ORDER_VALUE:
            return False, f"Order value ₹{value} exceeds limit ₹{MAX_ORDER_VALUE}"

        # Check daily spend limit
        self.reset_daily_spend()
        today = datetime.now(IST).strftime("%Y-%m-%d")
        current_spend = self._daily_spend.get(today, 0.0)
        if current_spend + value > MAX_DAILY_SPEND:
            return False, f"Daily spend limit ₹{MAX_DAILY_SPEND} would be exceeded"

        # Check market hours (weekdays 9:15 - 15:30 IST)
        now = datetime.now(IST)
        if now.weekday() >= 5:
            return False, "Market is closed"
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        if not (market_open <= now <= market_close):
            return False, "Market is closed"

        return True, ""

    def record_order(self, value: float) -> None:
        """Record an executed order's value toward the daily spend."""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        self._daily_spend[today] = self._daily_spend.get(today, 0.0) + value

    def is_paper_mode(self) -> bool:
        """Return whether paper trading mode is active."""
        return PAPER_TRADING

    def reset_daily_spend(self) -> None:
        """Reset spend tracking if it's a new trading day."""
        today = datetime.now(IST).strftime("%Y-%m-%d")
        # Remove entries for previous days
        old_keys = [k for k in self._daily_spend if k != today]
        for k in old_keys:
            del self._daily_spend[k]


guard = SafetyGuard()

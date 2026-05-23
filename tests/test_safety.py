"""Tests for src/safety.py SafetyGuard class."""

from datetime import datetime
from unittest.mock import patch

import pytest
from zoneinfo import ZoneInfo

from src.safety import SafetyGuard

IST = ZoneInfo("Asia/Kolkata")


def _make_weekday_market_open():
    """Return a datetime that is a weekday within market hours (Mon 10:00 IST)."""
    return datetime(2026, 5, 18, 10, 0, 0, tzinfo=IST)  # Monday


def _make_saturday():
    """Return a datetime that is a Saturday."""
    return datetime(2026, 5, 23, 10, 0, 0, tzinfo=IST)  # Saturday


def _make_after_hours():
    """Return a datetime that is a weekday but after market close (16:00 IST)."""
    return datetime(2026, 5, 18, 16, 0, 0, tzinfo=IST)  # Monday 4pm


class TestSafetyGuard:

    def test_valid_order(self):
        """A small valid order during market hours should pass."""
        guard = SafetyGuard()
        fake_now = _make_weekday_market_open()

        with patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            ok, reason = guard.validate_order(
                trading_symbol="RELIANCE",
                quantity=1,
                price=500,
                segment="CASH",
                transaction_type="BUY",
            )

        assert ok is True
        assert reason == ""

    def test_fno_blocked(self):
        """F&O orders should be blocked when ALLOW_FNO is False."""
        guard = SafetyGuard()
        fake_now = _make_weekday_market_open()

        with patch("src.safety.ALLOW_FNO", False), \
             patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            ok, reason = guard.validate_order(
                trading_symbol="NIFTY23JUNFUT",
                quantity=1,
                price=500,
                segment="FNO",
                transaction_type="BUY",
            )

        assert ok is False
        assert reason == "F&O trading is disabled"

    def test_order_value_exceeds_limit(self):
        """Orders exceeding MAX_ORDER_VALUE should be blocked."""
        guard = SafetyGuard()
        fake_now = _make_weekday_market_open()

        with patch("src.safety.MAX_ORDER_VALUE", 10000), \
             patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            ok, reason = guard.validate_order(
                trading_symbol="RELIANCE",
                quantity=100,
                price=200,
                segment="CASH",
                transaction_type="BUY",
            )

        assert ok is False
        assert "exceeds limit" in reason

    def test_daily_spend_exceeded(self):
        """Orders that would breach MAX_DAILY_SPEND should be blocked."""
        guard = SafetyGuard()
        fake_now = _make_weekday_market_open()

        with patch("src.safety.MAX_DAILY_SPEND", 50000), \
             patch("src.safety.MAX_ORDER_VALUE", 100000), \
             patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            # Record 45000 already spent today
            guard.record_order(45000)

            # Try to order 6000 more (total 51000 > 50000)
            ok, reason = guard.validate_order(
                trading_symbol="INFY",
                quantity=6,
                price=1000,
                segment="CASH",
                transaction_type="BUY",
            )

        assert ok is False
        assert "would be exceeded" in reason

    def test_market_closed_weekend(self):
        """Orders on weekends should be blocked."""
        guard = SafetyGuard()
        fake_now = _make_saturday()

        with patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            ok, reason = guard.validate_order(
                trading_symbol="RELIANCE",
                quantity=1,
                price=500,
                segment="CASH",
                transaction_type="BUY",
            )

        assert ok is False
        assert reason == "Market is closed"

    def test_market_closed_after_hours(self):
        """Orders after market hours (15:30) should be blocked."""
        guard = SafetyGuard()
        fake_now = _make_after_hours()

        with patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            ok, reason = guard.validate_order(
                trading_symbol="RELIANCE",
                quantity=1,
                price=500,
                segment="CASH",
                transaction_type="BUY",
            )

        assert ok is False
        assert reason == "Market is closed"

    def test_paper_mode(self):
        """is_paper_mode should reflect the PAPER_TRADING config."""
        guard = SafetyGuard()

        with patch("src.safety.PAPER_TRADING", True):
            assert guard.is_paper_mode() is True

        with patch("src.safety.PAPER_TRADING", False):
            assert guard.is_paper_mode() is False

    def test_reset_daily_spend(self):
        """reset_daily_spend should remove entries for previous days."""
        guard = SafetyGuard()

        # Manually inject yesterday's spend
        guard._daily_spend["2026-05-17"] = 30000
        guard._daily_spend["2026-05-18"] = 5000

        # Patch "today" to be 2026-05-18
        fake_now = datetime(2026, 5, 18, 10, 0, 0, tzinfo=IST)
        with patch("src.safety.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)

            guard.reset_daily_spend()

        # Yesterday's entry should be gone
        assert "2026-05-17" not in guard._daily_spend
        # Today's entry should remain
        assert "2026-05-18" in guard._daily_spend
        assert guard._daily_spend["2026-05-18"] == 5000

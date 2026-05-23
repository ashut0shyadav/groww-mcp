import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.evaluation import Evaluator


@pytest.fixture
def evaluator(tmp_path):
    return Evaluator(tmp_path)


def _make_trade(
    paper_order_id="ORD001",
    symbol="RELIANCE",
    action="BUY",
    quantity=10,
    fill_price=2500.0,
    strategy="RSI",
    indicators=None,
    timestamp="2026-05-23T10:00:00",
    **kwargs,
):
    trade = {
        "paper_order_id": paper_order_id,
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "fill_price": fill_price,
        "strategy": strategy,
        "indicators": indicators or {"rsi": 30},
        "timestamp": timestamp,
    }
    trade.update(kwargs)
    return trade


class TestLogTrade:
    def test_log_trade_buy(self, evaluator):
        """Log a BUY trade. Assert journal has 1 trade, trade_count=1."""
        trade = _make_trade(action="BUY")

        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.log_trade(trade)
            journal = evaluator.get_journal("2026-05-23")

        assert journal["trade_count"] == 1
        assert len(journal["trades"]) == 1
        assert journal["trades"][0]["action"] == "BUY"
        assert journal["trades"][0]["symbol"] == "RELIANCE"

    def test_log_trade_sell_with_pnl(self, evaluator):
        """Log a SELL trade with realized_pnl. Assert day_pnl updates and strategy updated."""
        trade = _make_trade(
            action="SELL",
            strategy="RSI",
            realized_pnl=500,
            return_pct=5.0,
            hold_duration_minutes=45,
        )

        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.log_trade(trade)
            journal = evaluator.get_journal("2026-05-23")

        assert journal["day_pnl"] == 500
        assert journal["trade_count"] == 1

        # Strategy should have been updated
        strategies = evaluator._load_strategies()
        assert "RSI" in strategies
        assert strategies["RSI"]["total_trades"] == 1
        assert strategies["RSI"]["winning_trades"] == 1


class TestGetJournal:
    def test_get_journal_today(self, evaluator):
        """Log trades, call get_journal(). Assert returns today's data."""
        trade = _make_trade()

        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.log_trade(trade)
            journal = evaluator.get_journal()

        assert journal["date"] == "2026-05-23"
        assert journal["trade_count"] == 1
        assert len(journal["trades"]) == 1

    def test_get_journal_specific_date(self, evaluator):
        """Log trade today, call get_journal('2026-01-01'). Assert empty."""
        trade = _make_trade()

        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.log_trade(trade)

        journal = evaluator.get_journal("2026-01-01")
        assert journal["trade_count"] == 0
        assert journal["trades"] == []

    def test_get_journal_empty(self, evaluator):
        """Call get_journal() on fresh evaluator. Assert trade_count=0, empty trades."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            journal = evaluator.get_journal()

        assert journal["trade_count"] == 0
        assert journal["trades"] == []
        assert journal["day_pnl"] == 0.0


class TestUpdateStrategy:
    def test_update_strategy_new(self, evaluator):
        """Create a new strategy entry. Assert total_trades=1, win_rate=100."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.update_strategy("MACD", pnl=200, return_pct=5.0, hold_minutes=60)

        strategies = evaluator._load_strategies()
        assert "MACD" in strategies
        assert strategies["MACD"]["total_trades"] == 1
        assert strategies["MACD"]["winning_trades"] == 1
        assert strategies["MACD"]["win_rate"] == 100.0

    def test_update_strategy_existing(self, evaluator):
        """Update same strategy twice: win then loss. Assert correct aggregation."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.update_strategy("MACD", pnl=200, return_pct=5.0, hold_minutes=60)
            evaluator.update_strategy("MACD", pnl=-100, return_pct=-2.0, hold_minutes=30)

        strategies = evaluator._load_strategies()
        entry = strategies["MACD"]
        assert entry["total_trades"] == 2
        assert entry["winning_trades"] == 1
        assert entry["losing_trades"] == 1
        assert entry["win_rate"] == 50.0
        assert entry["total_pnl"] == 100.0

    def test_update_strategy_empty_name(self, evaluator):
        """Call with strategy=''. Assert nothing is saved."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.update_strategy("", pnl=200, return_pct=5.0, hold_minutes=60)

        strategies = evaluator._load_strategies()
        assert strategies == {}


class TestGetStrategyScores:
    def test_get_strategy_scores_sorted(self, evaluator):
        """Add 'A' with win_rate 80% and 'B' with win_rate 40%. Assert 'A' first."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            # Strategy A: 4 wins, 1 loss -> 80%
            for _ in range(4):
                evaluator.update_strategy("A", pnl=100, return_pct=2.0, hold_minutes=30)
            evaluator.update_strategy("A", pnl=-50, return_pct=-1.0, hold_minutes=20)

            # Strategy B: 2 wins, 3 losses -> 40%
            for _ in range(2):
                evaluator.update_strategy("B", pnl=100, return_pct=2.0, hold_minutes=30)
            for _ in range(3):
                evaluator.update_strategy("B", pnl=-50, return_pct=-1.0, hold_minutes=20)

        scores = evaluator.get_strategy_scores()
        keys = list(scores.keys())
        assert keys[0] == "A"
        assert keys[1] == "B"
        assert scores["A"]["win_rate"] == 80.0
        assert scores["B"]["win_rate"] == 40.0


class TestCloseTrade:
    def test_close_trade(self, evaluator):
        """Log a sell trade, then close_trade. Assert enrichment with P&L data."""
        sell_trade = _make_trade(
            paper_order_id="SELL001",
            action="SELL",
            strategy="MACD",
        )

        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.log_trade(sell_trade)
            evaluator.close_trade(
                buy_order_id="BUY001",
                sell_order={"paper_order_id": "SELL001", "strategy": "MACD"},
                pnl=300.0,
                return_pct=3.5,
                hold_duration_minutes=90,
            )
            journal = evaluator.get_journal("2026-05-23")

        enriched_trade = journal["trades"][0]
        assert enriched_trade["realized_pnl"] == 300.0
        assert enriched_trade["return_pct"] == 3.5
        assert enriched_trade["hold_duration_minutes"] == 90
        assert enriched_trade["buy_order_id"] == "BUY001"


class TestLogRationale:
    def test_log_rationale(self, evaluator):
        """Log a trade, then add rationale. Assert rationale field added."""
        trade = _make_trade(paper_order_id="ORD_RAT")

        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.log_trade(trade)
            evaluator.log_rationale("ORD_RAT", "RSI crossed below 30, oversold signal")
            journal = evaluator.get_journal("2026-05-23")

        assert journal["trades"][0]["rationale"] == "RSI crossed below 30, oversold signal"

    def test_log_rationale_not_found(self, evaluator):
        """Call log_rationale with non-existent ID. Assert no crash."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            # Should not raise any exception
            evaluator.log_rationale("NONEXISTENT_ID", "some rationale")
            journal = evaluator.get_journal("2026-05-23")

        # No trades, nothing modified
        assert journal["trade_count"] == 0


class TestPerformanceSummary:
    def test_get_performance_summary_empty(self, evaluator):
        """Fresh evaluator, no portfolio.json. Assert all zeros."""
        summary = evaluator.get_performance_summary()

        assert summary["total_trades"] == 0
        assert summary["winning_trades"] == 0
        assert summary["losing_trades"] == 0
        assert summary["total_realized_pnl"] == 0.0
        assert summary["win_rate"] == 0.0
        assert summary["avg_pnl_per_trade"] == 0.0

    def test_get_performance_summary_with_data(self, tmp_path):
        """Create portfolio.json manually. Assert win_rate and avg_pnl calculated."""
        portfolio_data = {
            "total_trades": 10,
            "winning_trades": 7,
            "losing_trades": 3,
            "total_realized_pnl": 5000,
        }
        portfolio_file = tmp_path / "portfolio.json"
        portfolio_file.write_text(json.dumps(portfolio_data))

        ev = Evaluator(tmp_path)
        summary = ev.get_performance_summary()

        assert summary["total_trades"] == 10
        assert summary["win_rate"] == 70.0
        assert summary["avg_pnl_per_trade"] == 500.0


class TestPersistence:
    def test_persistence(self, tmp_path):
        """Log trade, create new Evaluator same dir. Assert journal persists."""
        ev1 = Evaluator(tmp_path)
        trade = _make_trade(paper_order_id="PERSIST001")

        with patch.object(ev1, "_today", return_value="2026-05-23"):
            ev1.log_trade(trade)

        # New evaluator instance pointing to same directory
        ev2 = Evaluator(tmp_path)
        journal = ev2.get_journal("2026-05-23")

        assert journal["trade_count"] == 1
        assert journal["trades"][0]["paper_order_id"] == "PERSIST001"


class TestRunningAverage:
    def test_running_average(self, evaluator):
        """Call update_strategy 3 times with return_pct 10, 20, 30. Assert avg converges."""
        with patch.object(evaluator, "_today", return_value="2026-05-23"):
            evaluator.update_strategy("VWAP", pnl=100, return_pct=10.0, hold_minutes=30)
            evaluator.update_strategy("VWAP", pnl=100, return_pct=20.0, hold_minutes=60)
            evaluator.update_strategy("VWAP", pnl=100, return_pct=30.0, hold_minutes=90)

        strategies = evaluator._load_strategies()
        entry = strategies["VWAP"]

        # Running average of 10, 20, 30 = 20.0
        assert entry["avg_return_pct"] == 20.0
        assert entry["total_trades"] == 3
        # Running average of hold_minutes 30, 60, 90 = 60.0
        assert entry["avg_hold_minutes"] == 60.0

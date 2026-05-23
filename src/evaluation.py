import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class Evaluator:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.journal_dir = data_dir / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.strategies_file = data_dir / "strategies.json"

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_journal(self, date: str) -> dict:
        """Reads journal file or returns empty structure."""
        path = self.journal_dir / f"{date}.json"
        if path.exists():
            return json.loads(path.read_text())
        return {"date": date, "trades": [], "day_pnl": 0.0, "trade_count": 0}

    def _save_journal(self, date: str, data: dict) -> None:
        """Writes journal file."""
        path = self.journal_dir / f"{date}.json"
        path.write_text(json.dumps(data, indent=2, default=str))

    def _load_strategies(self) -> dict:
        """Reads strategies.json or returns empty dict."""
        if self.strategies_file.exists():
            return json.loads(self.strategies_file.read_text())
        return {}

    def _save_strategies(self, data: dict) -> None:
        """Writes strategies.json."""
        self.strategies_file.write_text(json.dumps(data, indent=2, default=str))

    def _today(self) -> str:
        """Returns today's date string in IST."""
        return datetime.now(IST).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def log_trade(self, trade: dict) -> None:
        """Appends a trade to today's journal file.

        Trade dict has: paper_order_id, symbol, action (BUY/SELL), quantity,
        fill_price, strategy, indicators, timestamp.

        If it's a SELL with realized_pnl, also update the strategy leaderboard.
        """
        date = self._today()
        journal = self._load_journal(date)

        journal["trades"].append(trade)
        journal["trade_count"] = len(journal["trades"])

        # If SELL with realized_pnl, update day_pnl and strategy
        if trade.get("action") == "SELL" and "realized_pnl" in trade:
            journal["day_pnl"] += trade["realized_pnl"]
            strategy = trade.get("strategy", "")
            if strategy:
                self.update_strategy(
                    strategy=strategy,
                    pnl=trade["realized_pnl"],
                    return_pct=trade.get("return_pct", 0.0),
                    hold_minutes=trade.get("hold_duration_minutes", 0),
                )

        self._save_journal(date, journal)

    def close_trade(
        self,
        buy_order_id: str,
        sell_order: dict,
        pnl: float,
        return_pct: float,
        hold_duration_minutes: int,
    ) -> None:
        """Called when a SELL happens — enriches the sell journal entry with P&L data.

        Updates strategy scores.
        """
        date = self._today()
        journal = self._load_journal(date)

        # Find the sell trade entry and enrich it
        for trade in reversed(journal["trades"]):
            if trade.get("paper_order_id") == sell_order.get("paper_order_id"):
                trade["buy_order_id"] = buy_order_id
                trade["realized_pnl"] = pnl
                trade["return_pct"] = return_pct
                trade["hold_duration_minutes"] = hold_duration_minutes
                break

        # Update day_pnl
        journal["day_pnl"] = sum(
            t.get("realized_pnl", 0.0)
            for t in journal["trades"]
            if t.get("action") == "SELL" and "realized_pnl" in t
        )

        self._save_journal(date, journal)

        # Update strategy leaderboard
        strategy = sell_order.get("strategy", "")
        self.update_strategy(strategy, pnl, return_pct, hold_duration_minutes)

    def get_journal(self, date: str = None) -> dict:
        """Returns the journal for that date, or empty structure if no trades.

        If date is None, use today (IST).
        Includes: date, trades list, day_pnl, trade_count.
        """
        if date is None:
            date = self._today()
        return self._load_journal(date)

    def get_performance_summary(self) -> dict:
        """Reads from portfolio.json stats and recent journals for a comprehensive summary.

        Returns: win_rate, avg_pnl_per_trade, best_trade, worst_trade, daily_returns.
        """
        portfolio_file = self.data_dir / "portfolio.json"
        if portfolio_file.exists():
            portfolio = json.loads(portfolio_file.read_text())
        else:
            portfolio = {}

        total_trades = portfolio.get("total_trades", 0)
        winning_trades = portfolio.get("winning_trades", 0)
        losing_trades = portfolio.get("losing_trades", 0)
        total_realized_pnl = portfolio.get("total_realized_pnl", 0.0)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        avg_pnl_per_trade = (total_realized_pnl / total_trades) if total_trades > 0 else 0.0

        # Scan recent journals (last 7 days)
        today = datetime.now(IST)
        best_trade = None
        worst_trade = None
        daily_returns = []

        for i in range(7):
            from datetime import timedelta

            day = today - timedelta(days=i)
            date_str = day.strftime("%Y-%m-%d")
            journal = self._load_journal(date_str)

            if journal["trade_count"] > 0:
                daily_returns.append({"date": date_str, "pnl": journal["day_pnl"]})

                for trade in journal["trades"]:
                    if trade.get("action") != "SELL" or "realized_pnl" not in trade:
                        continue
                    pnl = trade["realized_pnl"]
                    trade_summary = {
                        "symbol": trade.get("symbol"),
                        "pnl": pnl,
                        "return_pct": trade.get("return_pct", 0.0),
                        "date": date_str,
                    }
                    if best_trade is None or pnl > best_trade["pnl"]:
                        best_trade = trade_summary
                    if worst_trade is None or pnl < worst_trade["pnl"]:
                        worst_trade = trade_summary

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_realized_pnl": total_realized_pnl,
            "win_rate": round(win_rate, 2),
            "avg_pnl_per_trade": round(avg_pnl_per_trade, 2),
            "best_trade": best_trade,
            "worst_trade": worst_trade,
            "daily_returns": daily_returns,
        }

    def get_strategy_scores(self) -> dict:
        """Returns strategies sorted by win_rate descending.

        Each strategy has: total_trades, winning_trades, losing_trades,
        win_rate, total_pnl, avg_return_pct, last_used.
        """
        strategies = self._load_strategies()
        sorted_strategies = dict(
            sorted(strategies.items(), key=lambda x: x[1].get("win_rate", 0), reverse=True)
        )
        return sorted_strategies

    def update_strategy(
        self, strategy: str, pnl: float, return_pct: float, hold_minutes: int
    ) -> None:
        """Updates the strategy entry in strategies.json.

        If strategy is empty string, skip (untagged trade).
        """
        if not strategy:
            return

        strategies = self._load_strategies()

        if strategy not in strategies:
            strategies[strategy] = {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_return_pct": 0.0,
                "avg_hold_minutes": 0.0,
                "last_used": "",
            }

        entry = strategies[strategy]
        entry["total_trades"] += 1

        if pnl > 0:
            entry["winning_trades"] += 1
        else:
            entry["losing_trades"] += 1

        entry["win_rate"] = round(
            entry["winning_trades"] / entry["total_trades"] * 100, 2
        )
        entry["total_pnl"] = round(entry["total_pnl"] + pnl, 2)

        # Running average for return_pct
        n = entry["total_trades"]
        entry["avg_return_pct"] = round(
            entry["avg_return_pct"] + (return_pct - entry["avg_return_pct"]) / n, 4
        )

        # Running average for hold_minutes
        entry["avg_hold_minutes"] = round(
            entry["avg_hold_minutes"] + (hold_minutes - entry["avg_hold_minutes"]) / n, 1
        )

        entry["last_used"] = self._today()

        strategies[strategy] = entry
        self._save_strategies(strategies)

    def log_rationale(self, paper_order_id: str, rationale: str) -> None:
        """Finds the trade in today's journal and adds a 'rationale' field.

        Useful for Claude to explain WHY it made a trade.
        """
        date = self._today()
        journal = self._load_journal(date)

        for trade in journal["trades"]:
            if trade.get("paper_order_id") == paper_order_id:
                trade["rationale"] = rationale
                break

        self._save_journal(date, journal)


# Module-level singleton
from src.config import DATA_DIR

evaluator = Evaluator(DATA_DIR)

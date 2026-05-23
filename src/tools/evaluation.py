"""MCP tools for the performance evaluation system."""

import json

from mcp.server.fastmcp import FastMCP

from src.evaluation import evaluator
from src.paper_engine import engine


def register_evaluation_tools(mcp: FastMCP):
    """Register all evaluation-related MCP tools on the given server."""

    @mcp.tool()
    async def get_paper_portfolio() -> str:
        """Get the current virtual paper trading portfolio.

        Returns balance, open positions with unrealized P&L,
        total realized P&L, total number of trades, and win/loss count.
        Use this to check your simulated portfolio state before making decisions.

        Returns:
            JSON string with portfolio details or error message.
        """
        try:
            portfolio = engine.get_portfolio()
            return json.dumps(portfolio, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_performance_summary() -> str:
        """Get comprehensive performance metrics for recent trading activity.

        Returns win rate, total P&L, average P&L per trade, best and worst
        trade from the last 7 days, and daily returns. Use this to evaluate
        overall trading effectiveness and identify trends.

        Returns:
            JSON string with performance metrics or error message.
        """
        try:
            summary = evaluator.get_performance_summary()
            return json.dumps(summary, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_trade_journal(date: str = "") -> str:
        """Get all trades for a specific date.

        Returns the trade journal entries for the given date, including
        entry/exit prices, P&L, and any logged rationale. Use this to
        review past trading decisions and learn from them.

        Args:
            date: Date in YYYY-MM-DD format. If empty, returns today's trades.

        Returns:
            JSON string with trade journal entries or error message.
        """
        try:
            journal = evaluator.get_journal(date or None)
            return json.dumps(journal, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_strategy_scores() -> str:
        """Get strategy leaderboard sorted by win rate.

        Shows which trading strategies are profitable and their performance
        metrics. Call this BEFORE making any trade decision to check which
        strategies are currently working.

        Returns:
            JSON string with strategy scores or error message.
        """
        try:
            scores = evaluator.get_strategy_scores()
            return json.dumps(scores, indent=2, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def log_trade_rationale(paper_order_id: str, rationale: str) -> str:
        """Record the reasoning behind a trade for later review.

        Use this after placing a paper trade to document why the trade
        was made. This helps with post-trade analysis and strategy
        improvement.

        Args:
            paper_order_id: The order ID from the paper trade.
            rationale: The reasoning and analysis behind the trade decision.

        Returns:
            Confirmation string or error message.
        """
        try:
            evaluator.log_rationale(paper_order_id, rationale)
            return f"Rationale logged for order {paper_order_id}"
        except Exception as e:
            return json.dumps({"error": str(e)})

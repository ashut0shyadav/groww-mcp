"""Groww MCP Server — trade stocks via Claude using Groww's official Trade API."""

from mcp.server.fastmcp import FastMCP

from src.tools.market import register_market_tools
from src.tools.analysis import register_analysis_tools
from src.tools.portfolio import register_portfolio_tools
from src.tools.trading import register_trading_tools
from src.tools.evaluation import register_evaluation_tools

mcp = FastMCP(
    "groww-trading",
    instructions=(
        "Use these tools to search Indian stocks, fetch live/historical prices, "
        "compute technical indicators, manage portfolio, and place trades on Groww. "
        "Paper trading mode is ON by default — trades execute against a virtual portfolio "
        "with real market prices.\n\n"
        "IMPORTANT: Before placing any trade, ALWAYS call get_strategy_scores to check "
        "which strategies are currently profitable. Prefer strategies with win_rate > 0.5 "
        "and positive total_pnl. Tag every trade with a strategy name.\n\n"
        "After each trading session, call get_trade_journal to review outcomes and "
        "get_performance_summary for overall metrics."
    ),
)

register_market_tools(mcp)
register_analysis_tools(mcp)
register_portfolio_tools(mcp)
register_trading_tools(mcp)
register_evaluation_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

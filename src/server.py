"""Groww MCP Server — trade stocks via Claude using Groww's official Trade API."""

from mcp.server.fastmcp import FastMCP

from src.tools.market import register_market_tools
from src.tools.analysis import register_analysis_tools
from src.tools.portfolio import register_portfolio_tools
from src.tools.trading import register_trading_tools

mcp = FastMCP(
    "groww-trading",
    instructions="Use these tools to search Indian stocks, fetch live/historical prices, "
    "compute technical indicators, manage portfolio, and place trades on Groww. "
    "Always check prices and indicators before suggesting trades. "
    "Paper trading mode is ON by default — real orders require explicit user confirmation.",
)

register_market_tools(mcp)
register_analysis_tools(mcp)
register_portfolio_tools(mcp)
register_trading_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

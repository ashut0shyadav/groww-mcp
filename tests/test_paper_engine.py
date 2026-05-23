import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.paper_engine import PaperEngine


@pytest.fixture
def engine(tmp_path):
    return PaperEngine(tmp_path, starting_balance=100000)


# 1. Fresh engine has correct initial state
def test_initial_portfolio(engine):
    portfolio = engine.get_portfolio()
    assert portfolio["balance"] == 100000
    assert portfolio["positions"] == {}
    assert portfolio["total_realized_pnl"] == 0.0
    assert portfolio["total_trades"] == 0
    assert portfolio["winning_trades"] == 0
    assert portfolio["losing_trades"] == 0


# 2. LIMIT BUY decreases balance and creates position
def test_buy_order_limit(engine):
    result = engine.execute_order(
        symbol="RELIANCE",
        quantity=10,
        transaction_type="BUY",
        order_type="LIMIT",
        price=1350,
        exchange="NSE",
    )
    assert result["status"] == "EXECUTED"
    portfolio = engine.get_portfolio()
    assert portfolio["balance"] == 100000 - 13500
    assert portfolio["positions"]["RELIANCE"]["quantity"] == 10
    assert portfolio["positions"]["RELIANCE"]["avg_price"] == 1350


# 3. Insufficient balance rejects the order
def test_buy_insufficient_balance(tmp_path):
    engine = PaperEngine(tmp_path, starting_balance=1000)
    result = engine.execute_order(
        symbol="RELIANCE",
        quantity=10,
        transaction_type="BUY",
        order_type="LIMIT",
        price=1350,
        exchange="NSE",
    )
    assert result["status"] == "REJECTED"
    assert result["reason"] == "Insufficient balance"


# 4. Sell at profit updates balance and pnl
def test_sell_order(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1350, exchange="NSE",
    )
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="SELL",
        order_type="LIMIT", price=1400, exchange="NSE",
    )
    portfolio = engine.get_portfolio()
    assert portfolio["balance"] == 100000 + 500
    assert "RELIANCE" not in portfolio["positions"]
    assert portfolio["total_realized_pnl"] == 500
    assert portfolio["winning_trades"] == 1


# 5. Sell at loss records losing trade
def test_sell_at_loss(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1350, exchange="NSE",
    )
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="SELL",
        order_type="LIMIT", price=1300, exchange="NSE",
    )
    portfolio = engine.get_portfolio()
    assert portfolio["total_realized_pnl"] == -500
    assert portfolio["losing_trades"] == 1


# 6. Sell more than held quantity is rejected
def test_sell_insufficient_quantity(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=5, transaction_type="BUY",
        order_type="LIMIT", price=1350, exchange="NSE",
    )
    result = engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="SELL",
        order_type="LIMIT", price=1400, exchange="NSE",
    )
    assert result["status"] == "REJECTED"


# 7. Sell without any position is rejected
def test_sell_without_position(engine):
    result = engine.execute_order(
        symbol="INFY", quantity=10, transaction_type="SELL",
        order_type="LIMIT", price=1500, exchange="NSE",
    )
    assert result["status"] == "REJECTED"


# 8. Buying more of same symbol averages position
def test_position_averaging(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1300, exchange="NSE",
    )
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1400, exchange="NSE",
    )
    portfolio = engine.get_portfolio()
    pos = portfolio["positions"]["RELIANCE"]
    assert pos["quantity"] == 20
    assert pos["avg_price"] == 1350
    assert pos["invested"] == 27000


# 9. Partial sell keeps remaining position at original avg_price
def test_partial_sell(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1000, exchange="NSE",
    )
    engine.execute_order(
        symbol="RELIANCE", quantity=5, transaction_type="SELL",
        order_type="LIMIT", price=1100, exchange="NSE",
    )
    portfolio = engine.get_portfolio()
    pos = portfolio["positions"]["RELIANCE"]
    assert pos["quantity"] == 5
    assert pos["avg_price"] == 1000
    # Balance: 100000 - 10000 (buy) + 5500 (sell) = 95500
    assert portfolio["balance"] == 95500


# 10. Order IDs are sequential PAPER_0001, PAPER_0002, PAPER_0003
def test_order_id_generation(engine):
    ids = []
    for i in range(3):
        result = engine.execute_order(
            symbol="RELIANCE", quantity=1, transaction_type="BUY",
            order_type="LIMIT", price=100, exchange="NSE",
        )
        ids.append(result["paper_order_id"])
    assert ids == ["PAPER_0001", "PAPER_0002", "PAPER_0003"]


# 11. get_holdings returns correct format for multiple positions
def test_get_holdings(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=5, transaction_type="BUY",
        order_type="LIMIT", price=1350, exchange="NSE",
    )
    engine.execute_order(
        symbol="INFY", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1500, exchange="NSE",
    )
    holdings = engine.get_holdings()
    assert len(holdings) == 2
    symbols = {h["trading_symbol"] for h in holdings}
    assert symbols == {"RELIANCE", "INFY"}
    for h in holdings:
        assert "quantity" in h
        assert "average_price" in h
        assert h["isin"] == "PAPER"


# 12. get_positions returns correct format
def test_get_positions(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=5, transaction_type="BUY",
        order_type="LIMIT", price=1350, exchange="NSE",
    )
    engine.execute_order(
        symbol="INFY", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1500, exchange="NSE",
    )
    positions = engine.get_positions()
    assert len(positions) == 2
    for p in positions:
        assert p["segment"] == "CASH"
        assert p["exchange"] == "NSE"
        assert p["product"] == "CNC"
        assert "trading_symbol" in p
        assert "quantity" in p
        assert "net_price" in p


# 13. get_orders returns all placed orders
def test_get_orders_all(engine):
    for _ in range(3):
        engine.execute_order(
            symbol="RELIANCE", quantity=1, transaction_type="BUY",
            order_type="LIMIT", price=100, exchange="NSE",
        )
    orders = engine.get_orders()
    assert len(orders["order_list"]) == 3


# 14. get_orders with date filter
def test_get_orders_by_date(engine):
    engine.execute_order(
        symbol="RELIANCE", quantity=1, transaction_type="BUY",
        order_type="LIMIT", price=100, exchange="NSE",
    )
    # The order timestamp starts with today's date in IST
    orders_today = engine.get_orders("2026-05-23")
    assert len(orders_today["order_list"]) >= 1
    # Non-matching date returns empty
    orders_other = engine.get_orders("2000-01-01")
    assert len(orders_other["order_list"]) == 0


# 15. get_order_status finds a placed order
def test_get_order_status_found(engine):
    result = engine.execute_order(
        symbol="RELIANCE", quantity=1, transaction_type="BUY",
        order_type="LIMIT", price=100, exchange="NSE",
    )
    order_id = result["paper_order_id"]
    status = engine.get_order_status(order_id)
    assert status["paper_order_id"] == order_id
    assert status["status"] == "EXECUTED"
    assert status["trading_symbol"] == "RELIANCE"


# 16. get_order_status returns NOT_FOUND for unknown ID
def test_get_order_status_not_found(engine):
    status = engine.get_order_status("PAPER_9999")
    assert status["status"] == "NOT_FOUND"


# 17. cancel_order on an already executed order
def test_cancel_executed_order(engine):
    result = engine.execute_order(
        symbol="RELIANCE", quantity=1, transaction_type="BUY",
        order_type="LIMIT", price=100, exchange="NSE",
    )
    order_id = result["paper_order_id"]
    cancel_result = engine.cancel_order(order_id)
    assert cancel_result["message"] == "Order already executed"


# 18. State persists across engine instances
def test_persistence(tmp_path):
    engine1 = PaperEngine(tmp_path, starting_balance=100000)
    engine1.execute_order(
        symbol="RELIANCE", quantity=10, transaction_type="BUY",
        order_type="LIMIT", price=1350, exchange="NSE",
    )

    # Create a new engine pointing to the same directory
    engine2 = PaperEngine(tmp_path, starting_balance=100000)
    portfolio = engine2.get_portfolio()
    assert portfolio["balance"] == 100000 - 13500
    assert portfolio["positions"]["RELIANCE"]["quantity"] == 10
    assert portfolio["total_trades"] == 1

    orders = engine2.get_orders()
    assert len(orders["order_list"]) == 1


# 19. MARKET order uses get_client().get_ltp() for fill price
@patch("src.paper_engine.get_client")
def test_buy_market_order(mock_get_client, tmp_path):
    mock_client = MagicMock()
    mock_client.get_ltp.return_value = 1500.0
    mock_client.SEGMENT_CASH = "CASH"
    mock_get_client.return_value = mock_client

    engine = PaperEngine(tmp_path, starting_balance=100000)
    result = engine.execute_order(
        symbol="RELIANCE",
        quantity=10,
        transaction_type="BUY",
        order_type="MARKET",
        price=0,
        exchange="NSE",
    )
    assert result["status"] == "EXECUTED"
    assert result["fill_price"] == 1500.0
    assert result["order_value"] == 15000.0
    mock_client.get_ltp.assert_called_once()

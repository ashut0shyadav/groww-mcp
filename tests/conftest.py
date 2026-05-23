import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set dummy env vars before any src imports
os.environ.setdefault("GROWW_API_KEY", "test_key")
os.environ.setdefault("GROWW_TOTP_SECRET", "JBSWY3DPEHPK3PXP")


@pytest.fixture
def mock_groww_client():
    """Return a MagicMock that mimics the GrowwAPI instance."""
    client = MagicMock()
    client.EXCHANGE_NSE = "NSE"
    client.EXCHANGE_BSE = "BSE"
    client.SEGMENT_CASH = "CASH"
    client.SEGMENT_FNO = "FNO"
    client.PRODUCT_CNC = "CNC"
    client.ORDER_TYPE_LIMIT = "LIMIT"
    client.ORDER_TYPE_MARKET = "MARKET"
    client.ORDER_TYPE_STOP_LOSS = "STOP_LOSS"
    client.ORDER_TYPE_STOP_LOSS_MARKET = "STOP_LOSS_MARKET"
    client.TRANSACTION_TYPE_BUY = "BUY"
    client.TRANSACTION_TYPE_SELL = "SELL"
    client.VALIDITY_DAY = "DAY"
    return client


@pytest.fixture
def patch_get_client(mock_groww_client):
    """Patch get_client to return the mock across all tool modules."""
    with patch("src.auth.get_client", return_value=mock_groww_client), \
         patch("src.tools.market.get_client", return_value=mock_groww_client), \
         patch("src.tools.analysis.get_client", return_value=mock_groww_client), \
         patch("src.tools.portfolio.get_client", return_value=mock_groww_client), \
         patch("src.tools.trading.get_client", return_value=mock_groww_client):
        yield mock_groww_client

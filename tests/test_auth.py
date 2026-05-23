"""Tests for src/auth.py — GrowwAuth token generation and caching."""

from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from src.auth import GrowwAuth

IST = ZoneInfo("Asia/Kolkata")


@patch("src.auth.GrowwAPI")
@patch("src.auth.pyotp")
def test_first_call_generates_token(mock_pyotp, mock_groww_api):
    """First call to get_client should generate a new token."""
    mock_pyotp.TOTP.return_value.now.return_value = "123456"
    mock_groww_api.get_access_token.return_value = "fake_token"
    mock_groww_api.return_value = MagicMock()

    auth = GrowwAuth()
    client = auth.get_client()

    mock_groww_api.get_access_token.assert_called_once()
    assert client is not None


@patch("src.auth.GrowwAPI")
@patch("src.auth.pyotp")
def test_second_call_uses_cache(mock_pyotp, mock_groww_api):
    """Second call to get_client should use cached client, not regenerate token."""
    mock_pyotp.TOTP.return_value.now.return_value = "123456"
    mock_groww_api.get_access_token.return_value = "fake_token"
    mock_groww_api.return_value = MagicMock()

    auth = GrowwAuth()
    client1 = auth.get_client()
    client2 = auth.get_client()

    mock_groww_api.get_access_token.assert_called_once()
    assert client1 is client2


@patch("src.auth.datetime")
@patch("src.auth.GrowwAPI")
@patch("src.auth.pyotp")
def test_refresh_after_expiry(mock_pyotp, mock_groww_api, mock_datetime):
    """Token should refresh when current time is past 6 AM and token was set before 6 AM today."""
    mock_pyotp.TOTP.return_value.now.return_value = "123456"
    mock_groww_api.get_access_token.return_value = "fake_token"
    mock_groww_api.return_value = MagicMock()

    # Today 10:00 AM IST (past the 6 AM expiry)
    today_10am = datetime(2025, 5, 20, 10, 0, 0, tzinfo=IST)
    mock_datetime.now.return_value = today_10am

    auth = GrowwAuth()
    # Set token_date to yesterday 10:00 AM IST (before today's 6 AM)
    auth._token_date = datetime(2025, 5, 19, 10, 0, 0, tzinfo=IST)
    # Pretend we already have a client (simulating a cached state)
    auth._client = MagicMock()

    auth.get_client()

    mock_groww_api.get_access_token.assert_called_once()


@patch("src.auth.datetime")
@patch("src.auth.GrowwAPI")
@patch("src.auth.pyotp")
def test_no_refresh_before_6am(mock_pyotp, mock_groww_api, mock_datetime):
    """Token should NOT refresh when current time is before 6 AM today."""
    mock_pyotp.TOTP.return_value.now.return_value = "123456"
    mock_groww_api.get_access_token.return_value = "fake_token"
    mock_groww_api.return_value = MagicMock()

    # Today 5:00 AM IST (before the 6 AM expiry threshold)
    today_5am = datetime(2025, 5, 20, 5, 0, 0, tzinfo=IST)
    mock_datetime.now.return_value = today_5am

    auth = GrowwAuth()
    # Set token_date to today 2:00 AM IST
    auth._token_date = datetime(2025, 5, 20, 2, 0, 0, tzinfo=IST)
    auth._client = MagicMock()

    auth.get_client()

    mock_groww_api.get_access_token.assert_not_called()

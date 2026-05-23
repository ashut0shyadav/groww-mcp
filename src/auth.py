from datetime import datetime
from zoneinfo import ZoneInfo

import pyotp
from growwapi import GrowwAPI

from src.config import GROWW_API_KEY, GROWW_TOTP_SECRET

IST = ZoneInfo("Asia/Kolkata")


class GrowwAuth:
    def __init__(self) -> None:
        self._client: GrowwAPI | None = None
        self._token_date: datetime | None = None

    def _is_expired(self) -> bool:
        if self._token_date is None:
            return True
        now = datetime.now(IST)
        # Token expires daily at 6:00 AM IST.
        # If we're past 6 AM and the token was generated before today's 6 AM, refresh.
        today_expiry = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if now >= today_expiry and self._token_date < today_expiry:
            return True
        return False

    def get_client(self) -> GrowwAPI:
        if self._is_expired():
            totp = pyotp.TOTP(GROWW_TOTP_SECRET).now()
            access_token = GrowwAPI.get_access_token(
                api_key=GROWW_API_KEY, totp=totp
            )
            self._client = GrowwAPI(access_token)
            self._token_date = datetime.now(IST)
        return self._client


auth = GrowwAuth()


def get_client() -> GrowwAPI:
    return auth.get_client()

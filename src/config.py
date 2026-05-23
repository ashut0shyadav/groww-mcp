import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}. See .env.example")
    return val


GROWW_API_KEY: str = _require("GROWW_API_KEY")
GROWW_TOTP_SECRET: str = _require("GROWW_TOTP_SECRET")

PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "true").lower() == "true"
PAPER_STARTING_BALANCE: int = int(os.getenv("PAPER_STARTING_BALANCE", "100000"))
MAX_ORDER_VALUE: int = int(os.getenv("MAX_ORDER_VALUE", "10000"))
MAX_DAILY_SPEND: int = int(os.getenv("MAX_DAILY_SPEND", "50000"))
ALLOW_FNO: bool = os.getenv("ALLOW_FNO", "false").lower() == "true"

DATA_DIR: Path = Path(__file__).parent.parent / "data"

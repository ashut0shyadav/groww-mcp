"""Quick script to verify Groww API credentials work.

Run: python scripts/test_connection.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.auth import get_client


def main():
    print("Connecting to Groww API...")
    try:
        groww = get_client()
        print("  ✓ Authentication successful")
    except Exception as e:
        print(f"  ✗ Authentication failed: {e}")
        sys.exit(1)

    print("\nFetching LTP for RELIANCE...")
    try:
        ltp = groww.get_ltp(
            segment=groww.SEGMENT_CASH,
            exchange_trading_symbols="NSE_RELIANCE",
        )
        price = ltp.get("NSE_RELIANCE", "N/A")
        print(f"  ✓ LTP for RELIANCE: ₹{price}")
    except Exception as e:
        print(f"  ✗ LTP fetch failed: {e}")
        sys.exit(1)

    print("\nFetching instruments list...")
    try:
        df = groww.get_all_instruments()
        print(f"  ✓ {len(df)} instruments loaded")
    except Exception as e:
        print(f"  ✗ Instruments fetch failed: {e}")
        sys.exit(1)

    print("\n✓ All checks passed — server is ready for Claude Code integration.")


if __name__ == "__main__":
    main()

"""Build the synthetic demo database. Usage: python scripts/seed.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.demo import reset_demo  # noqa: E402

if __name__ == "__main__":
    t0 = time.perf_counter()
    result = reset_demo()
    print(f"Seeded synthetic demo data for {result['demo_date']} in {time.perf_counter() - t0:.1f}s")
    for table, n in result["rows"].items():
        print(f"  {table:12s} {n:>7,}")

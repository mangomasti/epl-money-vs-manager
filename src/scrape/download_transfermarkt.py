"""
Download Transfermarkt tables from the public transfermarkt-datasets project
(github.com/dcaribou/transfermarkt-datasets, CC0 licence).

The snapshot is frozen at 6 July 2026, which covers our full
2014/15 to 2025/26 window.

Files are saved UNTOUCHED (still compressed) to data/raw/transfermarkt/.
"""
from pathlib import Path
import time

import requests

BASE_URL = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/{table}.csv.gz"
TABLES = ["games", "transfers", "players", "clubs"]
OUT_DIR = Path("data/raw/transfermarkt")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        response = requests.get(BASE_URL.format(table=table), timeout=120)
        response.raise_for_status()
        out_path = OUT_DIR / f"{table}.csv.gz"
        out_path.write_bytes(response.content)
        print(f"Saved {out_path}  ({len(response.content) / 1_000_000:.1f} MB)")
        time.sleep(1)


if __name__ == "__main__":
    main()
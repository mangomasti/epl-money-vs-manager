"""
Download each season's Premier League page from Wikipedia (2014-15 to 2025-26).
Pages are saved UNTOUCHED to data/raw/wikipedia/. Parsing happens separately.

Wikipedia asks automated tools to identify themselves with a descriptive
User-Agent, including a way to contact the owner.
"""
from pathlib import Path
import time

import requests

URL = "https://en.wikipedia.org/wiki/{label}_Premier_League"
OUT_DIR = Path("data/raw/wikipedia")
HEADERS = {
    "User-Agent": "epl-money-vs-manager/1.0 "
                  "(student portfolio project; https://github.com/mangomasti/epl-money-vs-manager)"
}

FIRST_SEASON, LAST_SEASON = 2014, 2025


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        session.headers.update(HEADERS)
        for year in range(FIRST_SEASON, LAST_SEASON + 1):
            label = f"{year}–{str(year + 1)[-2:]}"          # e.g. 2014–15 (an en dash, not a hyphen)
            response = session.get(URL.format(label=label), timeout=30)
            response.raise_for_status()
            out_path = OUT_DIR / f"pl_{year}.html"
            out_path.write_text(response.text, encoding="utf-8")
            print(f"Saved {out_path}  ({len(response.text) / 1000:.0f} KB)")
            time.sleep(1)


if __name__ == "__main__":
    main()
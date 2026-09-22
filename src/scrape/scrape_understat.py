"""
Scrape Premier League match-level xG from Understat, 2014/15 to 2025/26.

Understat's pages load their data from an internal JSON endpoint:
    https://understat.com/getLeagueData/EPL/<season start year>
It only responds to requests carrying the headers its own page sends.

Raw responses are saved UNTOUCHED to data/raw/understat/.
"""
from pathlib import Path
import time

import requests

URL = "https://understat.com/getLeagueData/EPL/{year}"
REFERER = "https://understat.com/league/EPL/{year}"
OUT_DIR = Path("data/raw/understat")

FIRST_SEASON = 2014   # 2014/15
LAST_SEASON = 2025    # 2025/26

HEADERS = {
    "X-Requested-With": "XMLHttpRequest",   # marks this as a background data request
    "User-Agent": "Mozilla/5.0 (student portfolio project: epl-money-vs-manager)",
}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with requests.Session() as session:
        session.headers.update(HEADERS)

        for year in range(FIRST_SEASON, LAST_SEASON + 1):
            response = session.get(
                URL.format(year=year),
                headers={"Referer": REFERER.format(year=year)},
                timeout=30,
            )
            response.raise_for_status()

            out_path = OUT_DIR / f"epl_{year}.json"
            out_path.write_text(response.text, encoding="utf-8")   # save exactly as received

            data = response.json()
            print(f"Saved {out_path}: {len(data['dates'])} matches, "
                  f"{len(data['teams'])} teams, {len(data['players'])} players")
            time.sleep(2)   # be polite


if __name__ == "__main__":
    main()
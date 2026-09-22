"""
Download Premier League match data from football-data.co.uk
for seasons 2014/15 to 2025/26. Files are saved untouched
into data/raw/football_data/.
"""
from pathlib import Path
import time

import requests

BASE_URL = "https://football-data.co.uk/mmz4281/{code}/E0.csv"
NOTES_URL = "https://football-data.co.uk/notes.txt"
OUT_DIR = Path("data/raw/football_data")

FIRST_SEASON = 2014   # 2014/15
LAST_SEASON = 2025    # 2025/26


def season_code(start_year: int) -> str:
    """Turn a start year into the site's code, e.g. 2014 -> '1415'."""
    return f"{str(start_year)[-2:]}{str(start_year + 1)[-2:]}"


def download(url: str, out_path: Path) -> None:
    """Download one file and save it exactly as received."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    out_path.write_bytes(response.content)
    print(f"Saved {out_path}  ({len(response.content):,} bytes)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(FIRST_SEASON, LAST_SEASON + 1):
        code = season_code(year)
        download(BASE_URL.format(code=code), OUT_DIR / f"E0_{code}.csv")
        time.sleep(1)
    download(NOTES_URL, OUT_DIR / "notes.txt")


if __name__ == "__main__":
    main()
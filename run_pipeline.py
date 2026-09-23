"""
Rebuild the whole project with one command.

    python run_pipeline.py              # rebuild everything from the saved raw data
    python run_pipeline.py --download   # re-download raw data first, then rebuild

Runs every step in dependency order and stops at the first failure.
"""
import argparse
import subprocess
import sys
import time

DOWNLOAD_STEPS = [
    ("Download football-data matches", "src/scrape/download_football_data.py"),
    ("Scrape Understat xG",            "src/scrape/scrape_understat.py"),
    ("Download Transfermarkt tables",  "src/scrape/download_transfermarkt.py"),
    ("Scrape Wikipedia season pages",  "src/scrape/scrape_wikipedia.py"),
]

BUILD_STEPS = [
    ("Clean football-data matches",            "src/clean/clean_football_data.py"),
    ("Validate matches (14 checks)",           "src/validate/validate_matches.py"),
    ("Clean Understat xG",                     "src/clean/clean_understat.py"),
    ("Join matches + xG",                      "src/clean/build_match_table.py"),
    ("Clean and classify transfers",           "src/clean/clean_transfers.py"),
    ("Build manager spells",                   "src/clean/build_managers.py"),
    ("Parse Wikipedia managerial changes",     "src/clean/clean_wikipedia_managers.py"),
    ("Reconcile managers with Wikipedia",      "src/clean/reconcile_managers.py"),
]


def run(steps: list) -> None:
    total = len(steps)
    for i, (name, script) in enumerate(steps, start=1):
        print(f"\n{'=' * 70}\n[{i}/{total}] {name}  ({script})\n{'=' * 70}")
        start = time.time()
        result = subprocess.run([sys.executable, script])
        seconds = time.time() - start

        if result.returncode != 0:
            print(f"\n❌ FAILED at step {i}/{total}: {name} ({seconds:.1f}s)")
            print("Fix the error above, then run the pipeline again.")
            sys.exit(result.returncode)
        print(f"✅ {name} ({seconds:.1f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild the EPL Money vs Manager dataset.")
    parser.add_argument("--download", action="store_true",
                        help="re-download raw data from the web before rebuilding")
    args = parser.parse_args()

    steps = (DOWNLOAD_STEPS if args.download else []) + BUILD_STEPS
    start = time.time()
    run(steps)
    print(f"\n🎉 Pipeline complete: {len(steps)} steps in {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
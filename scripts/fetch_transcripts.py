"""Fetch transcripts for videos fetched by fetch_videos.py."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    print(f"Transcript output directory: {DATA_DIR}")


if __name__ == "__main__":
    main()

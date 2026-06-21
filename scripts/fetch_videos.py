"""Fetch videos from creators listed in creators.txt."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREATORS_FILE = ROOT / "creators.txt"


def load_creators() -> list[str]:
    """Return creator channel IDs or handles, one per line."""
    if not CREATORS_FILE.exists():
        return []
    return [
        line.strip()
        for line in CREATORS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def main() -> None:
    creators = load_creators()
    print(f"Loaded {len(creators)} creator(s) from {CREATORS_FILE}")


if __name__ == "__main__":
    main()

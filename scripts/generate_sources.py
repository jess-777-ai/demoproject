"""Generate research/sources.md from fetched video and transcript data."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "research" / "sources.md"


def main() -> None:
    SOURCES_FILE.parent.mkdir(exist_ok=True)
    if not SOURCES_FILE.exists():
        SOURCES_FILE.write_text("# Sources\n\n", encoding="utf-8")
    print(f"Sources file: {SOURCES_FILE}")


if __name__ == "__main__":
    main()

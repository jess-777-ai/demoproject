"""Fetch latest videos from creators listed in creators.txt."""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREATORS_FILE = ROOT / "creators.txt"
ENV_FILE = ROOT / ".env"
OUTPUT_FILE = ROOT / "research" / "other" / "video_metadata.json"
API_BASE = "https://www.googleapis.com/youtube/v3"
CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")


def load_env(path: Path) -> dict[str, str]:
    """Parse KEY=value lines from a .env file."""
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def load_creators() -> list[str]:
    """Return creator names, handles, or channel IDs, one per line."""
    if not CREATORS_FILE.exists():
        return []
    return [
        line.strip()
        for line in CREATORS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def api_get(endpoint: str, params: dict[str, str], api_key: str) -> dict:
    """Call the YouTube Data API and return parsed JSON."""
    query = urllib.parse.urlencode({**params, "key": api_key})
    url = f"{API_BASE}/{endpoint}?{query}"
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"YouTube API error ({exc.code}): {body}") from exc


def resolve_channel(creator: str, api_key: str) -> tuple[str, str]:
    """Return (channel_id, display_name) for a creator entry."""
    if CHANNEL_ID_PATTERN.match(creator):
        data = api_get(
            "channels",
            {"part": "snippet", "id": creator},
            api_key,
        )
        items = data.get("items", [])
        if not items:
            raise ValueError(f"No channel found for ID: {creator}")
        snippet = items[0]["snippet"]
        return creator, snippet.get("title", creator)

    handle = creator[1:] if creator.startswith("@") else creator
    if creator.startswith("@"):
        data = api_get(
            "channels",
            {"part": "snippet", "forHandle": handle},
            api_key,
        )
        items = data.get("items", [])
        if items:
            channel_id = items[0]["id"]
            return channel_id, items[0]["snippet"].get("title", creator)

    data = api_get(
        "search",
        {
            "part": "snippet",
            "type": "channel",
            "q": creator,
            "maxResults": "1",
        },
        api_key,
    )
    items = data.get("items", [])
    if not items:
        raise ValueError(f"No channel found for: {creator}")
    item = items[0]
    channel_id = item["id"]["channelId"]
    title = item["snippet"].get("channelTitle", creator)
    return channel_id, title


def get_uploads_playlist_id(channel_id: str, api_key: str) -> str:
    """Return the uploads playlist ID for a channel."""
    data = api_get(
        "channels",
        {"part": "contentDetails", "id": channel_id},
        api_key,
    )
    items = data.get("items", [])
    if not items:
        raise ValueError(f"Could not load channel details for {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_latest_videos(
    creator: str, channel_id: str, channel_name: str, api_key: str, limit: int = 3
) -> list[dict]:
    """Return metadata for the latest videos on a channel."""
    playlist_id = get_uploads_playlist_id(channel_id, api_key)
    data = api_get(
        "playlistItems",
        {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": str(limit),
        },
        api_key,
    )

    videos: list[dict] = []
    for item in data.get("items", []):
        snippet = item["snippet"]
        video_id = snippet["resourceId"]["videoId"]
        videos.append(
            {
                "creator": channel_name,
                "title": snippet["title"],
                "upload_date": snippet["publishedAt"][:10],
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return videos


def main() -> None:
    env = load_env(ENV_FILE)
    api_key = env.get("YOUTUBE_API_KEY") or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("Error: YOUTUBE_API_KEY not set in .env or environment.", file=sys.stderr)
        sys.exit(1)

    creators = load_creators()
    if not creators:
        print(f"Error: no creators found in {CREATORS_FILE}", file=sys.stderr)
        sys.exit(1)

    all_videos: list[dict] = []
    for creator in creators:
        try:
            channel_id, channel_name = resolve_channel(creator, api_key)
            videos = fetch_latest_videos(creator, channel_id, channel_name, api_key)
            all_videos.extend(videos)
            print(f"{channel_name}: {len(videos)} video(s)")
        except (ValueError, RuntimeError) as exc:
            print(f"Skipping {creator!r}: {exc}", file=sys.stderr)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(all_videos, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(all_videos)} video(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

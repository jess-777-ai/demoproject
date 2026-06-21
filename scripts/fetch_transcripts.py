"""Fetch transcripts for videos listed in video_metadata.json."""

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
METADATA_FILE = ROOT / "research" / "other" / "video_metadata.json"
OUTPUT_DIR = ROOT / "research" / "youtube-transcripts"
API_ROOT = "https://api.supadata.ai/v1"
JOB_POLL_INTERVAL = 2
JOB_MAX_WAIT = 300


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


def slugify(*parts: str) -> str:
    """Build a filesystem-safe slug from one or more strings."""
    combined = "-".join(parts)
    slug = combined.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:200] or "untitled"


def load_videos() -> list[dict]:
    """Load video entries from video_metadata.json."""
    if not METADATA_FILE.exists():
        raise FileNotFoundError(f"Metadata file not found: {METADATA_FILE}")
    return json.loads(METADATA_FILE.read_text(encoding="utf-8"))


def api_request(url: str, api_key: str) -> tuple[int, dict]:
    """Send a GET request to Supadata and return (status_code, parsed_json)."""
    request = urllib.request.Request(
        url,
        headers={
            "x-api-key": api_key,
            "Accept": "application/json",
            "User-Agent": "demoproject-transcript-fetcher/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")

    try:
        data = json.loads(body) if body else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Supadata returned non-JSON response ({status})") from exc

    if status >= 400:
        error = data.get("error", "unknown")
        message = data.get("message", "Request failed")
        raise RuntimeError(f"Supadata API error ({status}): {error} - {message}")

    return status, data


def verify_api_key(api_key: str) -> None:
    """Confirm the API key is valid before fetching transcripts."""
    _, data = api_request(f"{API_ROOT}/me", api_key)
    plan = data.get("plan", "unknown")
    used = data.get("usedCredits", "?")
    maximum = data.get("maxCredits", "?")
    print(f"Supadata account OK - plan: {plan}, credits: {used}/{maximum}")


def extract_content(data: dict) -> str:
    """Pull plain text from a transcript or job-result payload."""
    content = data.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(chunk.get("text", "") for chunk in content).strip()
    raise RuntimeError("No transcript content in response")


def poll_transcript_job(job_id: str, api_key: str) -> str:
    """Poll an async transcript job until it completes or fails."""
    deadline = time.time() + JOB_MAX_WAIT
    while time.time() < deadline:
        _, data = api_request(f"{API_ROOT}/transcript/{job_id}", api_key)
        status = data.get("status")

        if status == "completed":
            return extract_content(data)
        if status == "failed":
            error = data.get("error") or {}
            message = error.get("message", "Transcript job failed")
            raise RuntimeError(message)

        time.sleep(JOB_POLL_INTERVAL)

    raise RuntimeError(f"Transcript job timed out after {JOB_MAX_WAIT}s")


def fetch_transcript(video_url: str, api_key: str) -> str:
    """Return plain-text transcript for a YouTube video URL."""
    params = urllib.parse.urlencode(
        {
            "url": video_url,
            "text": "true",
            "mode": "auto",
            "lang": "en",
        }
    )
    status, data = api_request(f"{API_ROOT}/transcript?{params}", api_key)

    if "jobId" in data:
        print("  async job started, waiting...")
        return poll_transcript_job(data["jobId"], api_key)

    if status in (200, 202):
        return extract_content(data)

    raise RuntimeError("Unexpected transcript response")


def build_markdown(video: dict, transcript: str) -> str:
    """Format video metadata and transcript as markdown."""
    return (
        f"# {video['title']}\n\n"
        f"Creator: {video['creator']}\n"
        f"Date: {video['upload_date']}\n"
        f"URL: {video['url']}\n\n"
        f"## Transcript\n\n"
        f"{transcript}\n"
    )


def main() -> None:
    env = load_env(ENV_FILE)
    api_key = env.get("SUPADATA_API_KEY") or env.get("SUPADATA_API_KEY".lower())
    if not api_key:
        print("Error: SUPADATA_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    try:
        verify_api_key(api_key)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "Check your key at https://supadata.ai (no spaces around = in .env)",
            file=sys.stderr,
        )
        sys.exit(1)

    videos = load_videos()
    if not videos:
        print(f"No videos found in {METADATA_FILE}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    saved = 0

    for index, video in enumerate(videos, start=1):
        filename = slugify(video["creator"], video["title"]) + ".md"
        output_path = OUTPUT_DIR / filename
        title = video["title"].encode("ascii", errors="replace").decode("ascii")

        try:
            print(f"[{index}/{len(videos)}] {title}")
            transcript = fetch_transcript(video["url"], api_key)
            output_path.write_text(build_markdown(video, transcript), encoding="utf-8")
            saved += 1
            print(f"  -> {output_path.name}")
        except RuntimeError as exc:
            print(f"  Skipped: {exc}", file=sys.stderr)

        if index < len(videos):
            time.sleep(0.5)

    print(f"Saved {saved}/{len(videos)} transcript(s) to {OUTPUT_DIR}")
    if saved == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Download videos from Google Ads Transparency Center.

Usage:
    python3 scripts/download.py <url_or_video_id> [output_dir]

Accepts:
    - Ads Transparency URL (needs playwright to extract video ID + metadata)
    - YouTube URL (youtube.com/watch?v=... or youtu.be/... or /shorts/...)
    - Raw YouTube video ID (e.g. ipgSCZ6TRxg)

Examples:
    python3 scripts/download.py ipgSCZ6TRxg
    python3 scripts/download.py "https://www.youtube.com/watch?v=ipgSCZ6TRxg"
    python3 scripts/download.py "https://adstransparency.google.com/advertiser/AR.../creative/CR...?region=US&format=VIDEO"
"""

import os
import re
import shutil
import subprocess
import sys

DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")


def sanitize_filename(name):
    """Remove characters not safe for filenames."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name[:80] if name else ""


def extract_from_ads_transparency(ads_url):
    """
    Extract YouTube video IDs and metadata from Ads Transparency page.
    Returns list of dicts: {id, title, channel, is_short}
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: playwright não instalado.")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    print("  Abrindo página com Playwright...")
    videos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(ads_url, timeout=30000)
        page.wait_for_timeout(8000)

        for frame in page.frames:
            if "youtube.com/embed/" not in frame.url:
                continue

            vid = frame.url.split("/embed/")[1].split("?")[0]
            if any(v["id"] == vid for v in videos):
                continue

            info = {"id": vid, "title": None, "channel": None, "is_short": False}

            try:
                title_el = frame.query_selector("a.ytmVideoInfoVideoTitle")
                if title_el:
                    href = title_el.get_attribute("href") or ""
                    info["title"] = title_el.inner_text().strip() or None
                    info["is_short"] = "/shorts/" in href

                channel_el = frame.query_selector(
                    "a.ytmVideoInfoChannelName, [class*='ytmVideoInfoChannel'] a"
                )
                if channel_el:
                    info["channel"] = channel_el.inner_text().strip() or None
            except Exception:
                pass

            videos.append(info)

        browser.close()

    return videos


def parse_input(arg):
    """Parse input and return list of video info dicts."""
    if "adstransparency.google.com" in arg:
        return extract_from_ads_transparency(arg)

    vid = None
    if "youtube.com/watch" in arg:
        m = re.search(r'v=([a-zA-Z0-9_-]{11})', arg)
        vid = m.group(1) if m else None
    elif "youtube.com/shorts/" in arg:
        vid = arg.split("/shorts/")[1].split("?")[0].split("/")[0]
    elif "youtu.be/" in arg:
        vid = arg.split("youtu.be/")[1].split("?")[0]
    elif re.match(r'^[a-zA-Z0-9_-]{11}$', arg):
        vid = arg

    if vid:
        return [{"id": vid, "title": None, "channel": None, "is_short": "shorts" in arg}]

    print(f"ERRO: não foi possível interpretar '{arg}' como video ID ou URL.")
    return []


def ensure_h264(filepath):
    """Check video codec; if not H.264, convert with ffmpeg."""
    if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
        return filepath

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name", "-of", "csv=p=0", filepath],
            capture_output=True, text=True, timeout=10,
        )
        codec = result.stdout.strip()
    except Exception:
        return filepath

    if codec in ("h264", ""):
        return filepath

    print(f"  Codec {codec} detectado — convertendo para H.264 (compatível com QuickTime)...")
    h264_path = filepath.replace(".mp4", "_h264.mp4")

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", filepath, "-c:v", "libx264", "-crf", "18",
             "-preset", "fast", "-c:a", "aac", "-b:a", "128k", h264_path],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and os.path.exists(h264_path):
            os.remove(filepath)
            os.rename(h264_path, filepath)
            print(f"  Conversão concluída.")
    except Exception as e:
        print(f"  Conversão falhou: {e}")

    return filepath


def download_video(video_info, output_dir):
    """Download a single video. Returns filepath on success, None on failure."""
    os.makedirs(output_dir, exist_ok=True)

    vid = video_info["id"]
    title = video_info.get("title")
    is_short = video_info.get("is_short", False)

    url = f"https://www.youtube.com/watch?v={vid}"

    if title:
        safe_title = sanitize_filename(title)
        filename_tpl = f"{safe_title}__{vid}.%(ext)s"
    else:
        filename_tpl = f"ad_%(id)s.%(ext)s"

    output_template = os.path.join(output_dir, filename_tpl)

    cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "-f", "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url,
    ]

    type_label = "Short" if is_short else "Video"
    print(f"  Baixando {type_label}: {vid}" + (f' — "{title}"' if title else ""))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        for f in os.listdir(output_dir):
            if vid in f and f.endswith(".mp4"):
                path = os.path.join(output_dir, f)
                path = ensure_h264(path)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"  Salvo: {path} ({size_mb:.1f} MB)")
                return path

    print(f"  ERRO: yt-dlp falhou para {vid}")
    if result.stderr:
        for line in result.stderr.strip().split("\n")[-3:]:
            print(f"    {line}")
    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else DOWNLOADS_DIR

    videos = parse_input(arg)
    if not videos:
        sys.exit(1)

    print()
    for v in videos:
        parts = [v["id"]]
        if v.get("title"):
            parts.append(f'"{v["title"]}"')
        if v.get("channel"):
            parts.append(f"by {v['channel']}")
        if v.get("is_short"):
            parts.append("(Short)")
        print(f"  → {' — '.join(parts)}")
    print()

    for v in videos:
        download_video(v, output_dir)


if __name__ == "__main__":
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        default_path = os.path.expanduser("~/Library/Caches/ms-playwright")
        if os.path.isdir(default_path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = default_path

    main()

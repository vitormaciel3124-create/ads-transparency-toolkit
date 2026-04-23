#!/usr/bin/env python3
"""
Download videos from Google Ads Transparency Center.

Usage:
    python3 download.py <url_or_video_id> [output_dir]

Accepts:
    - Ads Transparency URL (needs playwright to extract video ID)
    - YouTube URL (youtube.com/watch?v=... or youtu.be/...)
    - Raw YouTube video ID (e.g. ipgSCZ6TRxg)

Examples:
    python3 download.py ipgSCZ6TRxg
    python3 download.py "https://www.youtube.com/watch?v=ipgSCZ6TRxg"
    python3 download.py "https://adstransparency.google.com/advertiser/AR.../creative/CR...?region=US&platform=YOUTUBE"
"""

import os
import re
import subprocess
import sys


def extract_ids_from_ads_transparency(ads_url):
    """Use Playwright to extract YouTube video IDs from Ads Transparency page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: playwright not installed. Install with: pip3 install playwright && playwright install chromium")
        print("Or find the video ID manually in DevTools (iframe youtube.com/embed/VIDEO_ID)")
        sys.exit(1)

    print(f"Opening page with Playwright...")
    video_ids = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(ads_url, timeout=30000)
        page.wait_for_timeout(8000)

        for frame in page.frames:
            if "youtube.com/embed/" in frame.url:
                vid = frame.url.split("/embed/")[1].split("?")[0]
                if vid not in video_ids:
                    video_ids.append(vid)

        browser.close()

    return video_ids


def parse_input(arg):
    """Parse input and return list of YouTube video IDs."""
    if "adstransparency.google.com" in arg:
        return extract_ids_from_ads_transparency(arg)

    if "youtube.com/watch" in arg:
        m = re.search(r'v=([a-zA-Z0-9_-]{11})', arg)
        return [m.group(1)] if m else []

    if "youtu.be/" in arg:
        vid = arg.split("youtu.be/")[1].split("?")[0]
        return [vid]

    if re.match(r'^[a-zA-Z0-9_-]{11}$', arg):
        return [arg]

    print(f"Error: could not parse '{arg}' as a video ID or URL.")
    return []


def download(video_id, output_dir):
    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(output_dir, f"ad_%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "-o", output_template,
        url,
    ]

    print(f"Downloading {video_id}...")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        for f in os.listdir(output_dir):
            if video_id in f and f.endswith(".mp4"):
                path = os.path.join(output_dir, f)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"Saved: {path} ({size_mb:.1f} MB)")
                return path

    return None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "/Users/vitormaciel/Documents/CV/TRANSPARENCY DOWNLOAD"

    video_ids = parse_input(arg)
    if not video_ids:
        sys.exit(1)

    print(f"Found {len(video_ids)} video(s): {', '.join(video_ids)}\n")

    for vid in video_ids:
        download(vid, output_dir)


if __name__ == "__main__":
    main()

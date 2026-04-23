"""
Download video+audio from Google Ads Transparency Center.
Uses Playwright to intercept the YouTube player API response
and extract audio/video stream URLs.
"""

import json
import subprocess
import sys
import urllib.request

from playwright.sync_api import sync_playwright

TARGET_URL = (
    "https://adstransparency.google.com/advertiser/"
    "AR01610934807007592449/creative/"
    "CR09373715829452963841?region=US&platform=YOUTUBE"
)
OUTPUT_DIR = "/Users/vitormaciel/Downloads"


def download_stream(url, output_path):
    print(f"  Downloading to {output_path}...")
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = resp.read()
    with open(output_path, "wb") as f:
        f.write(data)
    print(f"  Done: {len(data):,} bytes ({len(data)//1024} KB)")
    return len(data)


def main():
    captured_formats = []
    video_urls_raw = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--autoplay-policy=no-user-gesture-required"])
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()

        def handle_response(response):
            url = response.url

            if "/youtubei/v1/player" in url:
                try:
                    data = response.json()
                    status = data.get("playabilityStatus", {}).get("status", "?")
                    print(f"\n>>> [PLAYER API] Status: {status}")

                    streaming = data.get("streamingData", {})
                    for key in ["adaptiveFormats", "formats"]:
                        formats = streaming.get(key, [])
                        if not formats:
                            continue
                        print(f">>> [PLAYER API] {len(formats)} {key} found")

                        for f in formats:
                            mime = f.get("mimeType", "")
                            itag = f.get("itag", 0)
                            stream_url = f.get("url", "")
                            clen = f.get("contentLength", "0")
                            quality = f.get("qualityLabel", f.get("audioQuality", ""))
                            bitrate = f.get("bitrate", 0)
                            is_audio = "audio" in mime

                            print(
                                f"    {'AUDIO' if is_audio else 'VIDEO'} itag={itag} "
                                f"{quality} {mime[:50]} {int(clen)//1024}KB "
                                f"bitrate={bitrate} url={'YES' if stream_url else 'NO'}"
                            )

                            if stream_url:
                                captured_formats.append({
                                    "itag": itag,
                                    "mime": mime,
                                    "url": stream_url,
                                    "contentLength": int(clen),
                                    "quality": quality,
                                    "bitrate": bitrate,
                                    "type": "AUDIO" if is_audio else "VIDEO",
                                })
                except Exception as e:
                    print(f">>> [PLAYER API] Error: {e}")

            if "googlevideo.com/videoplayback" in url:
                try:
                    from urllib.parse import parse_qs, urlparse
                    params = parse_qs(urlparse(url).query)
                    itag = params.get("itag", ["?"])[0]
                    mime = params.get("mime", ["?"])[0]
                    clen = params.get("clen", ["0"])[0]
                    key = f"{itag}_{mime}"
                    if key not in video_urls_raw:
                        video_urls_raw[key] = url
                        is_audio = "audio" in mime
                        print(f"    [STREAM] {'AUD' if is_audio else 'VID'} itag={itag} mime={mime} clen={clen}")
                except Exception:
                    pass

        page.on("response", handle_response)

        print(f"Opening: {TARGET_URL}")
        page.goto(TARGET_URL, timeout=30000)
        print("Page loaded. Waiting for content to render...")

        page.wait_for_timeout(5000)

        print("Looking for video player...")
        try:
            page.wait_for_selector("iframe[src*='youtube'], video, [data-creative-format]", timeout=15000)
            print("Found media element!")
        except Exception:
            print("No media element found directly, waiting more...")

        page.wait_for_timeout(5000)

        if not captured_formats:
            print("\nNo player API captured yet. Scrolling and clicking to trigger...")
            page.evaluate("window.scrollBy(0, 300)")
            page.wait_for_timeout(2000)

            try:
                frames = page.frames
                print(f"Found {len(frames)} frames")
                for frame in frames:
                    if "youtube" in frame.url:
                        print(f"  YouTube frame: {frame.url[:100]}")
                        try:
                            frame.click("video", timeout=3000)
                            print("  Clicked video in iframe!")
                        except Exception:
                            try:
                                frame.click(".ytp-large-play-button", timeout=3000)
                                print("  Clicked play button!")
                            except Exception:
                                print("  Could not click play")
            except Exception as e:
                print(f"  Frame interaction error: {e}")

            page.wait_for_timeout(8000)

        if not captured_formats:
            print("\nStill no player API. Let me check frames for video data...")
            for frame in page.frames:
                print(f"  Frame: {frame.url[:120]}")

            print("\nWaiting 15 more seconds for any late responses...")
            page.wait_for_timeout(15000)

        if not captured_formats and video_urls_raw:
            print(f"\nNo player API but captured {len(video_urls_raw)} raw videoplayback URLs")
            for key, url in video_urls_raw.items():
                from urllib.parse import parse_qs, urlparse
                params = parse_qs(urlparse(url).query)
                mime = params.get("mime", ["?"])[0]
                itag = params.get("itag", ["?"])[0]
                clen = params.get("clen", ["0"])[0]
                is_audio = "audio" in mime

                clean_url = url.split("&range=")[0]
                if "&rn=" in clean_url:
                    clean_url = clean_url.split("&rn=")[0]

                captured_formats.append({
                    "itag": int(itag) if itag != "?" else 0,
                    "mime": mime,
                    "url": clean_url,
                    "contentLength": int(clen),
                    "quality": "",
                    "bitrate": 0,
                    "type": "AUDIO" if is_audio else "VIDEO",
                })

        browser.close()

    if not captured_formats:
        print("\nERROR: No streams captured at all.")
        sys.exit(1)

    audio_streams = [f for f in captured_formats if f["type"] == "AUDIO" and f["url"]]
    video_streams = [f for f in captured_formats if f["type"] == "VIDEO" and f["url"]]

    print(f"\n{'='*60}")
    print(f"RESULT: {len(video_streams)} video + {len(audio_streams)} audio streams")
    print(f"{'='*60}")

    best_video = max(video_streams, key=lambda x: x.get("bitrate", 0) or x.get("contentLength", 0)) if video_streams else None
    best_audio = max(audio_streams, key=lambda x: x.get("bitrate", 0) or x.get("contentLength", 0)) if audio_streams else None

    video_path = None
    audio_path = None

    if best_video:
        ext = "mp4" if "mp4" in best_video["mime"] else "webm"
        video_path = f"{OUTPUT_DIR}/ad_video_stream.{ext}"
        print(f"\nBest video: itag={best_video['itag']} {best_video.get('quality','')} "
              f"{best_video.get('bitrate',0)}bps {best_video['mime'][:30]}")
        try:
            download_stream(best_video["url"], video_path)
        except Exception as e:
            print(f"  Download failed: {e}")
            video_path = None

    if best_audio:
        ext = "m4a" if "mp4" in best_audio["mime"] else "webm"
        audio_path = f"{OUTPUT_DIR}/ad_audio_stream.{ext}"
        print(f"\nBest audio: itag={best_audio['itag']} {best_audio.get('quality','')} "
              f"{best_audio.get('bitrate',0)}bps {best_audio['mime'][:30]}")
        try:
            download_stream(best_audio["url"], audio_path)
        except Exception as e:
            print(f"  Download failed: {e}")
            audio_path = None

    if video_path and audio_path:
        output = f"{OUTPUT_DIR}/ad_creative_final.mp4"
        print(f"\nMerging video + audio → {output}")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            output,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"\n*** SUCCESS! Video with audio saved to: {output} ***")
        else:
            print(f"\nFFmpeg error: {result.stderr[-300:]}")
    elif video_path:
        print(f"\nVideo-only (no audio found): {video_path}")
    else:
        print("\nNo downloadable streams found.")

    with open(f"{OUTPUT_DIR}/ad_streams_dump.json", "w") as f:
        json.dump(captured_formats, f, indent=2)
    print(f"Stream metadata saved to: {OUTPUT_DIR}/ad_streams_dump.json")


if __name__ == "__main__":
    main()

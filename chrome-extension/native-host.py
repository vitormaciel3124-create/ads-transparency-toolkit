#!/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
"""
Native Messaging Host for Ads Transparency Downloader.
Receives page URL from Chrome, extracts YouTube video ID via Playwright,
downloads using yt-dlp, reports progress back to the extension.
"""

import json
import os
import struct
import subprocess
import sys

os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")

OUTPUT_DIR = "/Users/vitormaciel/Documents/CV/TRANSPARENCY DOWNLOAD"
YT_DLP = "/opt/homebrew/bin/yt-dlp"


def read_message():
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length:
        return None
    length = struct.unpack("=I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    return json.loads(data.decode("utf-8"))


def send_message(msg):
    encoded = json.dumps(msg).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def extract_video_ids(page_url):
    """Use Playwright to extract YouTube video IDs from Ads Transparency page."""
    send_message({"type": "progress", "text": "Extraindo video ID..."})

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        send_message({"type": "error", "text": "playwright não instalado"})
        return []

    video_ids = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(page_url, timeout=30000)
        page.wait_for_timeout(8000)

        for frame in page.frames:
            if "youtube.com/embed/" in frame.url:
                vid = frame.url.split("/embed/")[1].split("?")[0]
                if vid not in video_ids:
                    video_ids.append(vid)

        browser.close()

    return video_ids


def download_video(video_id):
    """Download video using yt-dlp and report progress."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = os.path.join(OUTPUT_DIR, f"ad_%(id)s.%(ext)s")

    yt_dlp_bin = YT_DLP if os.path.exists(YT_DLP) else "yt-dlp"

    cmd = [
        yt_dlp_bin,
        "--cookies-from-browser", "chrome",
        "-f", "bestvideo+bestaudio/best",
        "--merge-output-format", "mp4",
        "--newline",
        "-o", output_template,
        url,
    ]

    send_message({"type": "progress", "text": f"Baixando {video_id}..."})

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            if "[download]" in line and "%" in line:
                try:
                    pct = line.split("%")[0].split()[-1]
                    send_message({"type": "progress", "text": f"Baixando... {pct}%"})
                except (IndexError, ValueError):
                    pass
            elif "[Merger]" in line:
                send_message({"type": "progress", "text": "Juntando áudio + vídeo..."})

        proc.wait()

        if proc.returncode == 0:
            filename = f"ad_{video_id}.mp4"
            filepath = os.path.join(OUTPUT_DIR, filename)

            if not os.path.exists(filepath):
                for f in os.listdir(OUTPUT_DIR):
                    if video_id in f:
                        filename = f
                        filepath = os.path.join(OUTPUT_DIR, f)
                        break

            return filename, filepath
        else:
            send_message({"type": "error", "text": f"yt-dlp falhou (code {proc.returncode})"})
            return None, None

    except FileNotFoundError:
        send_message({"type": "error", "text": "yt-dlp não encontrado. Instale: brew install yt-dlp"})
        return None, None
    except Exception as e:
        send_message({"type": "error", "text": str(e)})
        return None, None


def main():
    msg = read_message()
    if not msg:
        return

    if msg.get("action") == "download_page":
        page_url = msg.get("url", "")

        if "adstransparency.google.com" not in page_url:
            send_message({"type": "error", "text": "URL inválida"})
            return

        video_ids = extract_video_ids(page_url)

        if not video_ids:
            send_message({"type": "error", "text": "Nenhum vídeo YouTube encontrado nesta página"})
            return

        send_message({"type": "progress", "text": f"Encontrado: {', '.join(video_ids)}"})

        all_files = []
        for vid in video_ids:
            filename, filepath = download_video(vid)
            if filename:
                all_files.append(filename)

        if all_files:
            send_message({
                "type": "done",
                "filename": ", ".join(all_files),
                "path": OUTPUT_DIR,
            })
        elif not all_files and video_ids:
            pass  # error already sent by download_video


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "native-host.log")
        with open(log_path, "a") as lf:
            lf.write(f"CRASH: {e}\n")
            traceback.print_exc(file=lf)
        try:
            send_message({"type": "error", "text": str(e)})
        except Exception:
            pass

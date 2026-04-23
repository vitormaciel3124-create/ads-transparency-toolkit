#!/usr/bin/env python3
"""
Upload videos to YouTube via the YouTube Data API v3.

Usage:
    # Upload all videos from downloads/
    python3 scripts/upload.py

    # Upload specific files
    python3 scripts/upload.py downloads/video1.mp4 downloads/video2.mp4

    # Upload with custom privacy setting
    python3 scripts/upload.py --privacy public

    # Upload as Shorts (adds #Shorts to description)
    python3 scripts/upload.py --shorts

    # Dry run — list what would be uploaded without actually uploading
    python3 scripts/upload.py --dry-run

First-time setup:
    1. Create a project at https://console.cloud.google.com
    2. Enable "YouTube Data API v3"
    3. Create OAuth 2.0 credentials (Desktop App)
    4. Download client_secret.json to this project's root folder
    5. Run this script — it will open a browser for authorization
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPTS_DIR)
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, "downloads")
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")
CLIENT_SECRET_PATH = os.path.join(PROJECT_ROOT, "client_secret.json")
TOKEN_PATH = os.path.join(PROJECT_ROOT, ".youtube_token.json")
UPLOAD_LOG_PATH = os.path.join(REPORTS_DIR, "uploads.json")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

VALID_PRIVACY = ("public", "unlisted", "private")

# Max file size for YouTube (128 GB, but we warn above 10 GB)
WARN_SIZE_GB = 10


def load_upload_log():
    """Load existing upload log or return empty structure."""
    if os.path.exists(UPLOAD_LOG_PATH):
        with open(UPLOAD_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"uploads": [], "stats": {"total_uploaded": 0, "total_failed": 0}}


def save_upload_log(log):
    """Save upload log to JSON."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    log["last_updated"] = datetime.now().isoformat()
    with open(UPLOAD_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"  Log salvo em: {UPLOAD_LOG_PATH}")


def parse_folder_metadata(filepath):
    """Extract ad_date and region from folder name like '2026-04-22_US'."""
    parent = os.path.basename(os.path.dirname(filepath))
    match = re.match(r'^(\d{4}-\d{2}-\d{2})_([A-Z]{2,})$', parent)
    if match:
        return {"ad_date": match.group(1), "region": match.group(2)}
    return {"ad_date": None, "region": None}


def log_upload(log, filepath, video_id, title, privacy, success, error=None):
    """Add an upload entry to the log."""
    meta = parse_folder_metadata(filepath)
    entry = {
        "uploaded_at": datetime.now().isoformat(),
        "file": os.path.basename(filepath),
        "folder": os.path.basename(os.path.dirname(filepath)),
        "title": title,
        "privacy": privacy,
        "ad_date": meta["ad_date"],
        "region": meta["region"],
        "success": success,
    }
    if success and video_id:
        entry["video_id"] = video_id
        entry["url"] = f"https://youtu.be/{video_id}"
        log["stats"]["total_uploaded"] += 1
    else:
        entry["error"] = str(error) if error else "unknown"
        log["stats"]["total_failed"] += 1
    log["uploads"].append(entry)
    return log


def check_dependencies():
    """Verify Google API libraries are installed."""
    missing = []
    try:
        import google.oauth2.credentials  # noqa: F401
    except ImportError:
        missing.append("google-auth")
    try:
        import google_auth_oauthlib.flow  # noqa: F401
    except ImportError:
        missing.append("google-auth-oauthlib")
    try:
        import googleapiclient.discovery  # noqa: F401
    except ImportError:
        missing.append("google-api-python-client")

    if missing:
        print("ERRO: Dependências faltando. Instale com:")
        print(f"  pip install {' '.join(missing)}")
        sys.exit(1)


def authenticate():
    """Authenticate with YouTube API via OAuth 2.0. Returns a YouTube service."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None

    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            if not os.path.exists(CLIENT_SECRET_PATH):
                print(f"ERRO: Arquivo '{CLIENT_SECRET_PATH}' não encontrado.")
                print()
                print("  Siga estes passos:")
                print("  1. Acesse https://console.cloud.google.com")
                print("  2. Crie um projeto ou selecione um existente")
                print("  3. Ative a 'YouTube Data API v3'")
                print("  4. Crie credenciais OAuth 2.0 (tipo 'App para computador')")
                print("  5. Baixe o JSON e salve como 'client_secret.json' na raiz do projeto")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(
                port=5050,
                prompt="select_account consent",
                open_browser=True,
            )

        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
        print("  Token salvo para futuras execuções.")

    return build("youtube", "v3", credentials=creds)


def title_from_filename(filename):
    """Generate a clean title from the MP4 filename."""
    name = os.path.splitext(filename)[0]
    # Remove the YouTube ID suffix (e.g. __KAuRtYi7lfg)
    name = re.sub(r'__[a-zA-Z0-9_-]{11}$', '', name)
    # Remove leading numeric prefixes like "294063_"
    name = re.sub(r'^\d+_', '', name)
    name = name.replace('_', ' ').strip()
    return name[:100] if name else filename


def find_videos(paths=None):
    """Find MP4 files to upload. Searches subfolders like downloads/2026-04-22_US/."""
    if paths:
        files = []
        for p in paths:
            if os.path.isdir(p):
                for f in sorted(os.listdir(p)):
                    if f.lower().endswith(".mp4"):
                        files.append(os.path.abspath(os.path.join(p, f)))
            elif os.path.isfile(p) and p.lower().endswith(".mp4"):
                files.append(os.path.abspath(p))
            elif os.path.isfile(p):
                print(f"  SKIP: {p} (não é .mp4)")
            else:
                print(f"  SKIP: {p} (não encontrado)")
        return files

    if not os.path.isdir(DOWNLOADS_DIR):
        print(f"  Pasta '{DOWNLOADS_DIR}' não encontrada.")
        return []

    files = []
    for root, dirs, filenames in os.walk(DOWNLOADS_DIR):
        for f in sorted(filenames):
            if f.lower().endswith(".mp4"):
                files.append(os.path.join(root, f))
    return sorted(files)


def upload_video(youtube, filepath, privacy="unlisted", as_shorts=False, category_id="22"):
    """Upload a single video to YouTube. Returns video ID on success."""
    from googleapiclient.http import MediaFileUpload

    filename = os.path.basename(filepath)
    title = title_from_filename(filename)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)

    description = f"Uploaded via Ads Transparency Toolkit — {datetime.now().strftime('%Y-%m-%d')}"
    if as_shorts:
        description = "#Shorts\n" + description

    print(f"\n  Uploading: {filename}")
    print(f"  Título:    {title}")
    print(f"  Tamanho:   {size_mb:.1f} MB")
    print(f"  Privacy:   {privacy}")

    if size_mb > WARN_SIZE_GB * 1024:
        print(f"  AVISO: Arquivo muito grande ({size_mb:.0f} MB). O upload pode demorar.")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        filepath,
        mimetype="video/mp4",
        resumable=True,
        chunksize=10 * 1024 * 1024,  # 10 MB chunks
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Progresso: {pct}%", end="\r")

    video_id = response.get("id")
    print(f"  Upload concluído! https://youtu.be/{video_id}")
    return video_id


def main():
    parser = argparse.ArgumentParser(
        description="Upload de vídeos para o YouTube via API v3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 scripts/upload.py
  python3 scripts/upload.py downloads/video.mp4
  python3 scripts/upload.py --privacy public --shorts
  python3 scripts/upload.py --dry-run
        """,
    )

    parser.add_argument("files", nargs="*", help="Arquivos MP4 para upload (default: todos em downloads/)")
    parser.add_argument("--privacy", default="unlisted", choices=VALID_PRIVACY,
                        help="Privacidade: public, unlisted, private (default: unlisted)")
    parser.add_argument("--shorts", action="store_true", help="Marcar como YouTube Shorts")
    parser.add_argument("--category", default="22", help="ID da categoria do YouTube (default: 22 = People & Blogs)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas listar o que seria enviado")
    parser.add_argument("--yes", "-y", action="store_true", help="Pular confirmação interativa")

    args = parser.parse_args()

    check_dependencies()

    videos = find_videos(args.files if args.files else None)

    if not videos:
        print("\n  Nenhum vídeo MP4 encontrado para upload.")
        print(f"  Coloque arquivos .mp4 em: {DOWNLOADS_DIR}")
        sys.exit(1)

    print(f"\n  YouTube Upload — {len(videos)} vídeo(s) encontrado(s)")
    print(f"  Privacidade: {args.privacy}")
    if args.shorts:
        print("  Modo: YouTube Shorts")
    print()

    for i, f in enumerate(videos, 1):
        name = os.path.basename(f)
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  {i:>3}. {name}  ({size_mb:.1f} MB)")

    if args.dry_run:
        print("\n  [DRY RUN] Nenhum upload realizado.")
        return

    if not args.yes:
        print()
        confirm = input("  Confirmar upload? (s/N): ").strip().lower()
        if confirm not in ("s", "sim", "y", "yes"):
            print("  Upload cancelado.")
            return

    youtube = authenticate()
    log = load_upload_log()

    success = 0
    failed = 0
    uploaded_ids = []

    for i, filepath in enumerate(videos, 1):
        filename = os.path.basename(filepath)
        title = title_from_filename(filename)
        print(f"\n  [{i}/{len(videos)}]", end="")
        try:
            vid_id = upload_video(
                youtube, filepath,
                privacy=args.privacy,
                as_shorts=args.shorts,
                category_id=args.category,
            )
            if vid_id:
                success += 1
                uploaded_ids.append(vid_id)
                log = log_upload(log, filepath, vid_id, title, args.privacy, success=True)
            else:
                failed += 1
                log = log_upload(log, filepath, None, title, args.privacy, success=False, error="No video ID returned")
        except Exception as e:
            print(f"  ERRO: {e}")
            failed += 1
            log = log_upload(log, filepath, None, title, args.privacy, success=False, error=e)

    save_upload_log(log)

    print(f"\n  {'=' * 50}")
    print(f"  Upload concluído!")
    print(f"  Sucesso: {success}  |  Falha: {failed}")
    if uploaded_ids:
        print(f"\n  Vídeos enviados:")
        for vid_id in uploaded_ids:
            print(f"    https://youtu.be/{vid_id}")
    print(f"  Total histórico: {log['stats']['total_uploaded']} enviados, {log['stats']['total_failed']} falhas")
    print(f"  {'=' * 50}\n")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Meta Ads Library — Save and analyze reports.

This script is designed for the MCP workflow:
  1. The Cursor agent uses MCP DevTools to navigate + scroll + extract ad data
  2. The agent passes the extracted JSON to this script via --json-file or stdin
  3. This script analyzes the data and saves a structured report

Can also build the Meta Ads Library URL for the agent to navigate to.

Usage:
    # Build URL for the agent to navigate to
    python3 scripts/meta_analyze.py --build-url --query "nike" --country US

    # Save report from JSON extracted by MCP (piped from agent)
    echo '{"ads": [...]}' | python3 scripts/meta_analyze.py --from-stdin --query "nike" --country US

    # Save report from a JSON file
    python3 scripts/meta_analyze.py --json-file /tmp/extracted.json --query "nike" --country US
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import urlencode

SCRIPTS_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR     = os.path.dirname(SCRIPTS_DIR)
REPORTS_DIR  = os.path.join(ROOT_DIR, "reports")
META_BASE    = "https://www.facebook.com/ads/library"


# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------

def build_url(query=None, page_id=None, country="US", active_only=False, fmt="video"):
    params = {
        "active_status": "active" if active_only else "all",
        "ad_type":       "all",
        "country":       country,
        "media_type":    fmt if fmt != "all" else "all",
    }
    if page_id:
        params["view_all_page_id"] = page_id
    elif query:
        params["q"] = query
        params["search_type"] = "keyword_unordered"
    return f"{META_BASE}/?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(ads, search_params):
    advertiser_counts = Counter(
        ad.get("advertiser_name") or "Unknown" for ad in ads
    )
    unique_lib_ids = {ad["library_id"] for ad in ads if ad.get("library_id")}

    return {
        "summary": {
            "total_found":         len(ads),
            "unique_library_ids":  len(unique_lib_ids),
            "unique_advertisers":  len(advertiser_counts),
        },
        "top_advertisers": [
            {"name": name, "count": count}
            for name, count in advertiser_counts.most_common(15)
        ],
        "search_params": search_params,
    }


# ---------------------------------------------------------------------------
# Report I/O
# ---------------------------------------------------------------------------

def save_report(report, label, country):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w-]", "_", str(label or "meta"))[:30]
    filename = f"meta_{safe}_{country}_{ts}.json"
    path = os.path.join(REPORTS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def print_report(report):
    analysis  = report["analysis"]
    summary   = analysis["summary"]
    creatives = report["creatives"]

    print(f"\n{'=' * 60}")
    print(f"  META ADS LIBRARY — Relatório")
    print(f"{'=' * 60}")
    print(f"  Total de vídeos encontrados:  {summary['total_found']}")
    print(f"  Library IDs únicos:           {summary['unique_library_ids']}")
    print(f"  Anunciantes únicos:           {summary['unique_advertisers']}")

    if analysis.get("top_advertisers"):
        print(f"\n  Top Anunciantes:")
        for adv in analysis["top_advertisers"]:
            print(f"    {adv['count']:3}x  {adv['name']}")

    print(f"\n  Criativos ({len(creatives)}):")
    for i, c in enumerate(creatives, 1):
        lib_id = c.get("library_id") or "sem-id"
        name   = c.get("advertiser_name") or "?"
        date   = c.get("start_date") or "?"
        active = "ativo" if c.get("is_active") else ("inativo" if c.get("is_active") is False else "?")
        print(f"    {i:3}. [{lib_id}] {name} — {date} ({active})")

    path = report.get("_path", "")
    if path:
        print(f"\n  Relatório: {path}")

    print(f"{'=' * 60}\n")
    print("  Para baixar:")
    rp = path or "reports/meta_ARQUIVO.json"
    print(f"    python3 scripts/meta_download.py --report {rp} --all")
    print(f"    python3 scripts/meta_download.py --report {rp} --top 5\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Meta Ads Library — análise e relatório (sem Playwright, para uso com MCP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow MCP (o agente faz tudo via DevTools, este script só salva):
  1. Agente: navigate_page → URL gerada por --build-url
  2. Agente: evaluate_script → scrollAndLoad + extractAds
  3. Agente: chama este script com --from-stdin ou --json-file
  4. Este script: analisa + salva JSON em reports/

Exemplos:
  python3 scripts/meta_analyze.py --build-url --query "nike" --country US
  echo '{"ads":[...]}' | python3 scripts/meta_analyze.py --from-stdin -q "nike" -c US
  python3 scripts/meta_analyze.py --json-file /tmp/mcp_extract.json -q "nike" -c US
        """,
    )
    parser.add_argument("--query",       "-q", help="Palavra-chave de busca")
    parser.add_argument("--page-id",           help="ID numérico da página Facebook")
    parser.add_argument("--country",     "-c", default="US", help="Código do país (default: US)")
    parser.add_argument("--active-only",       action="store_true", help="Apenas anúncios ativos")
    parser.add_argument("--format",            default="video", choices=["video", "image", "all"])
    # URL builder mode
    parser.add_argument("--build-url",         action="store_true", help="Apenas imprimir a URL para o agente navegar")
    # Input modes (MCP workflow)
    parser.add_argument("--from-stdin",        action="store_true", help="Ler JSON extraído do stdin")
    parser.add_argument("--json-file",         help="Caminho para JSON extraído pelo agente")

    args = parser.parse_args()

    country = args.country.upper()

    # --- Build URL mode ---
    if args.build_url:
        if not args.query and not args.page_id:
            print("ERRO: Forneça --query ou --page-id com --build-url")
            sys.exit(1)
        url = build_url(args.query, args.page_id, country, args.active_only, args.format)
        print(url)
        return

    # --- Load extracted data ---
    raw = None
    if args.from_stdin:
        raw = json.load(sys.stdin)
    elif args.json_file:
        with open(args.json_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        parser.print_help()
        print("\nERRO: Use --build-url, --from-stdin ou --json-file")
        sys.exit(1)

    # Accept both {ads: [...]} and [{...}, ...] formats
    if isinstance(raw, list):
        ads = raw
    elif isinstance(raw, dict):
        ads = raw.get("ads", raw.get("creatives", []))
    else:
        print("ERRO: formato JSON não reconhecido")
        sys.exit(1)

    if not ads:
        print("  Nenhum criativo nos dados recebidos.")
        sys.exit(0)

    # --- Analyze and save ---
    search_params = {
        "query":       args.query,
        "page_id":     args.page_id,
        "country":     country,
        "active_only": args.active_only,
        "format":      args.format,
        "platform":    "meta",
        "source_url":  build_url(args.query, args.page_id, country, args.active_only, args.format),
    }

    analysis = analyze(ads, search_params)

    report = {
        "generated_at": datetime.now().isoformat(),
        "platform":     "meta",
        "analysis":     analysis,
        "creatives": [
            {
                "library_id":      ad.get("library_id"),
                "advertiser_name": ad.get("advertiser_name"),
                "advertiser_page": ad.get("advertiser_page"),
                "video_url":       ad.get("video_url"),
                "start_date":      ad.get("start_date"),
                "is_active":       ad.get("is_active"),
                "ad_url":          ad.get("ad_url"),
                "format":          "video",
            }
            for ad in ads
        ],
    }

    path = save_report(report, args.query or args.page_id, country)
    report["_path"] = path
    print_report(report)


if __name__ == "__main__":
    main()

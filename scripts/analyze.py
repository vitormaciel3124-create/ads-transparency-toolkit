#!/usr/bin/env python3
"""
Analyze ads from Google Ads Transparency Center.

Scrapes a listing page, extracts all creatives, and produces
a structured report with stalk-level analysis.

Usage:
    python3 scripts/analyze.py "https://adstransparency.google.com/?region=US&domain=robloxos.com&format=VIDEO&preset-date=Yesterday"
    python3 scripts/analyze.py --domain robloxos.com --region US --date Yesterday
    python3 scripts/analyze.py --domain robloxos.com --region BR --date "Last 30 days" --max-scroll 80
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import quote, urlencode, urlparse, parse_qs

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports")
BASE_URL = "https://adstransparency.google.com"


def build_url(domain=None, advertiser=None, region="US", fmt="VIDEO", date="Yesterday"):
    params = {"region": region}
    if domain:
        params["domain"] = domain
    if fmt:
        params["format"] = fmt
    if date:
        params["preset-date"] = date

    if advertiser:
        return f"{BASE_URL}/advertiser/{advertiser}?{urlencode(params)}"
    return f"{BASE_URL}/?{urlencode(params)}"


def parse_url(url):
    """Extract search parameters from an Ads Transparency URL."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    info = {
        "url": url,
        "region": qs.get("region", ["US"])[0],
        "format": qs.get("format", [None])[0],
        "date": qs.get("preset-date", [None])[0],
        "domain": qs.get("domain", [None])[0],
    }
    # Extract advertiser ID from path if present
    if "/advertiser/" in parsed.path:
        parts = parsed.path.split("/advertiser/")[1].split("/")
        info["advertiser_id"] = parts[0] if parts else None
    return info


def scrape_creatives(url, max_scroll=50):
    """Scrape all creative cards from the listing page."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: playwright não instalado.")
        print("  pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"  Abrindo página...")
    creatives = []
    total_reported = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, timeout=30000)
        page.wait_for_timeout(5000)

        # Try to get total count from the page
        try:
            count_els = page.query_selector_all("[class*='count'], [class*='total']")
            for el in count_els:
                text = el.inner_text()
                if "anúncio" in text.lower() or "ad" in text.lower():
                    total_reported = text.strip()
                    break
        except Exception:
            pass

        if total_reported:
            print(f"  Página reporta: {total_reported}")

        # Scroll to load all ads
        prev_count = 0
        stale_rounds = 0

        for scroll_i in range(max_scroll):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

            links = page.query_selector_all("a[href*='/creative/']")
            current_count = len(links)

            if current_count > prev_count:
                stale_rounds = 0
                if (scroll_i + 1) % 5 == 0:
                    print(f"  Scroll {scroll_i + 1}: {current_count} criativos carregados...")
            else:
                stale_rounds += 1
                if stale_rounds >= 4:
                    print(f"  Scroll parou em {current_count} criativos (sem novos após {stale_rounds} tentativas)")
                    break

            prev_count = current_count

        # Extract data from each <creative-preview> card
        cards = page.query_selector_all("creative-preview")
        if not cards:
            cards = page.query_selector_all("a[href*='/creative/']")
        print(f"  Extraindo dados de {len(cards)} cards...")

        seen_urls = set()
        for card in cards:
            try:
                # Find the creative link inside the card
                link = card.query_selector("a[href*='/creative/']") if card.evaluate("el => el.tagName") != "A" else card
                if not link:
                    continue

                href = link.get_attribute("href") or ""
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Parse IDs from URL
                advertiser_id = None
                creative_id = None
                if "/advertiser/" in href:
                    parts = href.split("/advertiser/")[1]
                    advertiser_id = parts.split("/")[0]
                if "/creative/" in href:
                    cr_part = href.split("/creative/")[1]
                    creative_id = cr_part.split("?")[0]

                # Extract metadata using the Angular component structure
                meta = card.evaluate("""el => {
                    let root = el.closest('creative-preview') || el;
                    let nameEl = root.querySelector('.advertiser-name, [class*="advertiser-name"]');
                    let verifiedEl = root.querySelector('.verified, [class*="verified"]');
                    let iconLink = root.querySelector('a');
                    let iconText = iconLink ? iconLink.textContent.trim() : '';

                    return {
                        name: nameEl ? nameEl.textContent.trim() : null,
                        verified: !!verifiedEl,
                        icon: iconText
                    };
                }""")

                advertiser_name = meta.get("name")
                is_verified = meta.get("verified", False)
                icon_text = (meta.get("icon") or "").lower().strip()

                format_map = {"videocam": "video", "image": "image", "text_snippet": "text", "web": "web"}
                format_type = format_map.get(icon_text, "video" if icon_text == "videocam" else icon_text or "unknown")

                full_url = href if href.startswith("http") else BASE_URL + href

                creatives.append({
                    "creative_id": creative_id,
                    "advertiser_id": advertiser_id,
                    "advertiser_name": advertiser_name,
                    "url": full_url,
                    "format": format_type,
                    "verified": is_verified,
                })
            except Exception:
                continue

        browser.close()

    return creatives, total_reported


def analyze(creatives, search_params, total_reported):
    """Produce stalk analysis from scraped creatives."""
    total = len(creatives)

    # Unique creatives (by creative_id)
    creative_ids = [c["creative_id"] for c in creatives if c["creative_id"]]
    unique_creatives = len(set(creative_ids))
    repeated = {cid: count for cid, count in Counter(creative_ids).items() if count > 1}

    # By advertiser
    advertisers = Counter()
    advertiser_names = {}
    for c in creatives:
        aid = c["advertiser_id"] or "unknown"
        advertisers[aid] += 1
        if c["advertiser_name"]:
            advertiser_names[aid] = c["advertiser_name"]

    # By format
    formats = Counter(c["format"] for c in creatives)

    # Verified ratio
    verified_count = sum(1 for c in creatives if c["verified"])

    analysis = {
        "summary": {
            "total_found": total,
            "total_reported_by_page": total_reported,
            "unique_creatives": unique_creatives,
            "repeated_creatives": len(repeated),
            "advertisers_count": len(advertisers),
            "verified_count": verified_count,
        },
        "top_advertisers": [
            {
                "id": aid,
                "name": advertiser_names.get(aid, "?"),
                "ad_count": count,
            }
            for aid, count in advertisers.most_common(20)
        ],
        "repeated_creatives": [
            {"creative_id": cid, "count": count}
            for cid, count in sorted(repeated.items(), key=lambda x: -x[1])[:20]
        ],
        "format_distribution": dict(formats.most_common()),
        "search_params": search_params,
    }

    return analysis


def print_report(analysis, creatives):
    """Print a human-readable report to the terminal."""
    s = analysis["summary"]
    params = analysis["search_params"]

    print()
    print("=" * 60)
    print("  RELATÓRIO DE ANÁLISE — Ads Transparency Center")
    print("=" * 60)

    print(f"\n  Domínio:    {params.get('domain', '—')}")
    print(f"  Região:     {params.get('region', '—')}")
    print(f"  Período:    {params.get('date', '—')}")
    print(f"  Formato:    {params.get('format', 'Todos')}")

    print(f"\n{'─' * 60}")
    print(f"  Total reportado pela página:  {s['total_reported_by_page'] or '?'}")
    print(f"  Total extraído:               {s['total_found']}")
    print(f"  Criativos únicos:             {s['unique_creatives']}")
    print(f"  Criativos repetidos:          {s['repeated_creatives']}")
    print(f"  Anunciantes distintos:        {s['advertisers_count']}")
    print(f"  Verificados:                  {s['verified_count']}")

    print(f"\n{'─' * 60}")
    print("  DISTRIBUIÇÃO POR FORMATO")
    for fmt, count in analysis["format_distribution"].items():
        bar = "█" * min(count, 40)
        print(f"    {fmt:<15} {count:>4}  {bar}")

    print(f"\n{'─' * 60}")
    print("  TOP ANUNCIANTES")
    for i, adv in enumerate(analysis["top_advertisers"][:15], 1):
        verified = " ✓" if any(
            c["verified"] for c in creatives if c["advertiser_id"] == adv["id"]
        ) else ""
        print(f"    {i:>2}. {adv['name']:<35} {adv['ad_count']:>4} anúncios{verified}")

    if analysis["repeated_creatives"]:
        print(f"\n{'─' * 60}")
        print("  CRIATIVOS MAIS REPETIDOS")
        for item in analysis["repeated_creatives"][:10]:
            print(f"    CR {item['creative_id'][:20]}...  ×{item['count']}")

    print(f"\n{'─' * 60}")
    print("  LISTA DE CRIATIVOS (para seleção de download)")
    print(f"  {'#':>4}  {'Anunciante':<30} {'ID Criativo':<25} {'Fmt':<10}")
    print(f"  {'─'*4}  {'─'*30} {'─'*25} {'─'*10}")
    for i, c in enumerate(creatives, 1):
        name = (c["advertiser_name"] or "?")[:30]
        cid = (c["creative_id"] or "?")[:25]
        print(f"  {i:>4}  {name:<30} {cid:<25} {c['format']:<10}")

    print(f"\n{'=' * 60}")
    print(f"  Use batch_download.py para baixar criativos selecionados")
    print(f"  Exemplo: python3 scripts/batch_download.py --report <report.json> --select 1,2,3")
    print(f"{'=' * 60}\n")


def save_report(analysis, creatives, search_params):
    """Save report JSON to reports/ directory."""
    os.makedirs(REPORTS_DIR, exist_ok=True)

    domain = search_params.get("domain", "unknown")
    region = search_params.get("region", "XX")
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = re.sub(r'[^a-zA-Z0-9._-]', '_', f"{domain}_{region}_{date_str}")
    filepath = os.path.join(REPORTS_DIR, f"{filename}.json")

    report = {
        "generated_at": datetime.now().isoformat(),
        "analysis": analysis,
        "creatives": creatives,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"  Relatório salvo em: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Analisa anúncios do Google Ads Transparency Center",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 scripts/analyze.py "https://adstransparency.google.com/?region=US&domain=robloxos.com&format=VIDEO&preset-date=Yesterday"
  python3 scripts/analyze.py --domain robloxos.com --region BR --date "Last 30 days"
  python3 scripts/analyze.py --domain robloxos.com --region US --max-scroll 100
        """,
    )

    parser.add_argument("url", nargs="?", help="URL completa do Ads Transparency Center")
    parser.add_argument("--domain", help="Domínio para pesquisar (ex: robloxos.com)")
    parser.add_argument("--region", default="US", help="Código do país (default: US)")
    parser.add_argument("--date", default="Yesterday", help="Período (Yesterday, Last 7 days, Last 30 days)")
    parser.add_argument("--format", default="VIDEO", dest="fmt", help="Formato: VIDEO, IMAGE, TEXT (default: VIDEO)")
    parser.add_argument("--max-scroll", type=int, default=50, help="Máximo de scrolls para carregar anúncios (default: 50)")

    args = parser.parse_args()

    if args.url:
        url = args.url
        search_params = parse_url(url)
    elif args.domain:
        url = build_url(domain=args.domain, region=args.region, fmt=args.fmt, date=args.date)
        search_params = {
            "url": url,
            "domain": args.domain,
            "region": args.region,
            "format": args.fmt,
            "date": args.date,
        }
    else:
        parser.print_help()
        print("\nERRO: Forneça uma URL ou --domain")
        sys.exit(1)

    print(f"\n  Ads Transparency Analyzer")
    print(f"  URL: {url}\n")

    creatives, total_reported = scrape_creatives(url, max_scroll=args.max_scroll)

    if not creatives:
        print("\n  Nenhum criativo encontrado nesta página.")
        sys.exit(1)

    analysis = analyze(creatives, search_params, total_reported)
    print_report(analysis, creatives)
    save_report(analysis, creatives, search_params)


if __name__ == "__main__":
    # Ensure Playwright finds browsers on macOS
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        default_path = os.path.expanduser("~/Library/Caches/ms-playwright")
        if os.path.isdir(default_path):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = default_path

    main()

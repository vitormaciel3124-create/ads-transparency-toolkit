#!/usr/bin/env python3
"""
Analyze ads using the Chrome instance managed by Chrome DevTools MCP.

Instead of launching a separate Playwright/Chromium instance, this script
connects to the Chrome browser that MCP already has running via CDP
(Chrome DevTools Protocol). This avoids duplicate browser instances and
lets the Cursor agent see the same browser it controls via MCP tools.

Usage:
    python3 scripts/analyze_mcp.py --domain robloxos.com --region US --date Yesterday
    python3 scripts/analyze_mcp.py --domain robloxos.com --region BR --max-scroll 30
    python3 scripts/analyze_mcp.py --cdp-url http://127.0.0.1:9222 --domain example.com

Requirements:
    - Chrome DevTools MCP server running (starts Chrome automatically)
    - playwright (pip install playwright)
    - The MCP Chrome instance must be reachable via CDP (default port 9222)
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)
REPORTS_DIR = os.path.join(ROOT_DIR, "reports")
BASE_URL = "https://adstransparency.google.com"

DEFAULT_CDP_URL = "http://127.0.0.1:9222"
MCP_USER_DATA_DIR = os.path.expanduser("~/.cache/chrome-devtools-mcp/chrome-profile-stable")


def find_cdp_endpoint():
    """Try to discover the CDP endpoint from MCP's Chrome instance."""
    import urllib.request
    for port in [9222, 9223, 9224]:
        try:
            url = f"http://127.0.0.1:{port}/json/version"
            req = urllib.request.urlopen(url, timeout=2)
            data = json.loads(req.read())
            ws_url = data.get("webSocketDebuggerUrl")
            if ws_url:
                return f"http://127.0.0.1:{port}"
        except Exception:
            continue
    return None


def build_url(domain=None, region="US", fmt="VIDEO", date="Yesterday"):
    from urllib.parse import urlencode
    params = {"region": region}
    if domain:
        params["domain"] = domain
    if fmt:
        params["format"] = fmt
    if date:
        params["preset-date"] = date
    return f"{BASE_URL}/?{urlencode(params)}"


def scrape_creatives_via_cdp(url, cdp_url=None, max_scroll=50):
    """Scrape creatives by connecting to the MCP Chrome instance via CDP."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: playwright nao instalado. pip install playwright")
        sys.exit(1)

    cdp_url = cdp_url or find_cdp_endpoint()
    use_cdp = cdp_url is not None

    print(f"  Modo: {'CDP (Chrome do MCP)' if use_cdp else 'Standalone (novo Chrome)'}")
    if use_cdp:
        print(f"  CDP endpoint: {cdp_url}")

    creatives = []
    total_reported = None

    with sync_playwright() as p:
        if use_cdp:
            browser = p.chromium.connect_over_cdp(cdp_url)
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()
        else:
            print("  AVISO: CDP nao encontrado, lancando Chrome standalone")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})

        page.goto(url, timeout=30000)
        page.wait_for_timeout(5000)

        try:
            count_text = page.evaluate("""() => {
                const text = document.body.innerText;
                const m = text.match(/(Cerca de |About )?([\\d.,]+\\s*(mil|thousand)?\\s*(anúncios|ads))/i);
                return m ? m[0] : null;
            }""")
            total_reported = count_text
        except Exception:
            pass

        if total_reported:
            print(f"  Pagina reporta: {total_reported}")

        for btn_text in ["See all ads", "Ver mais resultados", "See all", "Ver todos"]:
            try:
                btn = page.query_selector(f"material-button:has-text('{btn_text}')")
                if btn and btn.is_visible():
                    print(f"  Clicando '{btn_text}'...")
                    btn.click()
                    page.wait_for_timeout(3000)
            except Exception:
                pass

        prev_count = 0
        stale_rounds = 0

        for scroll_i in range(max_scroll):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

            try:
                more_btn = page.query_selector("material-button.search-improvements-see-more-button")
                if more_btn and more_btn.is_visible():
                    more_btn.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

            links = page.query_selector_all("a[href*='/creative/']")
            current_count = len(links)

            if current_count > prev_count:
                stale_rounds = 0
                if (scroll_i + 1) % 5 == 0:
                    print(f"  Scroll {scroll_i + 1}: {current_count} criativos...")
            else:
                stale_rounds += 1
                if stale_rounds >= 5:
                    print(f"  Scroll parou em {current_count} criativos (stale)")
                    break

            prev_count = current_count

        creatives = page.evaluate("""() => {
            const cards = document.querySelectorAll('creative-preview');
            const result = [];
            const seen = new Set();

            cards.forEach(card => {
                const link = card.querySelector("a[href*='/creative/']");
                if (!link) return;
                const href = link.href || '';
                if (seen.has(href)) return;
                seen.add(href);

                const match = href.match(/advertiser\\/(AR\\w+)\\/creative\\/(CR\\w+)/);
                const nameEl = card.querySelector('.advertiser-name, [class*="advertiser-name"]');
                const verifiedEl = card.querySelector('.verified, [class*="verified"]');
                const iconLink = card.querySelector('a');
                const iconText = iconLink ? iconLink.textContent.trim().toLowerCase() : '';

                const formatMap = {videocam: 'video', image: 'image', text_snippet: 'text', web: 'web'};

                result.push({
                    creative_id: match ? match[2] : null,
                    advertiser_id: match ? match[1] : null,
                    advertiser_name: nameEl ? nameEl.textContent.trim() : null,
                    url: href.startsWith('http') ? href : 'https://adstransparency.google.com' + href,
                    format: formatMap[iconText] || 'video',
                    verified: !!verifiedEl
                });
            });

            return result;
        }""")

        print(f"  Extraidos {len(creatives)} criativos unicos")

        if use_cdp:
            page.close()
        else:
            browser.close()

    return creatives, total_reported


def analyze(creatives, search_params, total_reported):
    """Produce analysis from scraped creatives (same logic as analyze.py)."""
    total = len(creatives)
    creative_ids = [c["creative_id"] for c in creatives if c["creative_id"]]
    unique_creatives = len(set(creative_ids))
    repeated = {cid: count for cid, count in Counter(creative_ids).items() if count > 1}

    advertisers = Counter()
    advertiser_names = {}
    for c in creatives:
        aid = c["advertiser_id"] or "unknown"
        advertisers[aid] += 1
        if c["advertiser_name"]:
            advertiser_names[aid] = c["advertiser_name"]

    formats = Counter(c["format"] for c in creatives)
    verified_count = sum(1 for c in creatives if c["verified"])

    return {
        "summary": {
            "total_found": total,
            "total_reported_by_page": total_reported,
            "unique_creatives": unique_creatives,
            "repeated_creatives": len(repeated),
            "advertisers_count": len(advertisers),
            "verified_count": verified_count,
        },
        "top_advertisers": [
            {"id": aid, "name": advertiser_names.get(aid, "?"), "ad_count": count}
            for aid, count in advertisers.most_common(20)
        ],
        "repeated_creatives": [
            {"creative_id": cid, "count": count}
            for cid, count in sorted(repeated.items(), key=lambda x: -x[1])[:20]
        ],
        "format_distribution": dict(formats.most_common()),
        "search_params": search_params,
    }


def print_report(analysis, creatives):
    """Print a human-readable report."""
    s = analysis["summary"]
    params = analysis["search_params"]

    print()
    print("=" * 60)
    print("  RELATORIO — Ads Transparency (via MCP Chrome)")
    print("=" * 60)

    print(f"\n  Dominio:    {params.get('domain', '-')}")
    print(f"  Regiao:     {params.get('region', '-')}")
    print(f"  Periodo:    {params.get('date', '-')}")
    print(f"  Formato:    {params.get('format', 'Todos')}")

    print(f"\n{'-' * 60}")
    print(f"  Total reportado:   {s['total_reported_by_page'] or '?'}")
    print(f"  Total extraido:    {s['total_found']}")
    print(f"  Criativos unicos:  {s['unique_creatives']}")
    print(f"  Repetidos:         {s['repeated_creatives']}")
    print(f"  Anunciantes:       {s['advertisers_count']}")
    print(f"  Verificados:       {s['verified_count']}")

    print(f"\n{'-' * 60}")
    print("  TOP ANUNCIANTES")
    for i, adv in enumerate(analysis["top_advertisers"][:15], 1):
        print(f"    {i:>2}. {adv['name']:<35} {adv['ad_count']:>4} anuncios")

    print(f"\n{'-' * 60}")
    print(f"  {'#':>4}  {'Anunciante':<30} {'ID Criativo':<25} {'Fmt':<10}")
    print(f"  {'-'*4}  {'-'*30} {'-'*25} {'-'*10}")
    for i, c in enumerate(creatives[:50], 1):
        name = (c["advertiser_name"] or "?")[:30]
        cid = (c["creative_id"] or "?")[:25]
        print(f"  {i:>4}  {name:<30} {cid:<25} {c['format']:<10}")
    if len(creatives) > 50:
        print(f"  ... e mais {len(creatives) - 50} criativos")
    print(f"\n{'=' * 60}\n")


def save_report(analysis, creatives, search_params):
    """Save report JSON."""
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

    print(f"  Relatorio salvo em: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(
        description="Analisa anuncios usando o Chrome do MCP (via CDP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python3 scripts/analyze_mcp.py --domain robloxos.com
  python3 scripts/analyze_mcp.py --domain robloxos.com --region BR --date "Last 30 days"
  python3 scripts/analyze_mcp.py --cdp-url http://127.0.0.1:9222 --domain example.com
        """,
    )

    parser.add_argument("--domain", required=True, help="Dominio para pesquisar")
    parser.add_argument("--region", default="US", help="Codigo do pais (default: US)")
    parser.add_argument("--date", default="Yesterday", help="Periodo (Yesterday, Last 7 days, Last 30 days)")
    parser.add_argument("--format", default="VIDEO", dest="fmt", help="Formato: VIDEO, IMAGE, TEXT")
    parser.add_argument("--max-scroll", type=int, default=50, help="Maximo de scrolls (default: 50)")
    parser.add_argument("--cdp-url", default=None, help=f"CDP endpoint (default: auto-detect ou {DEFAULT_CDP_URL})")

    args = parser.parse_args()

    url = build_url(domain=args.domain, region=args.region, fmt=args.fmt, date=args.date)
    search_params = {
        "url": url,
        "domain": args.domain,
        "region": args.region,
        "format": args.fmt,
        "date": args.date,
    }

    print(f"\n  Ads Transparency Analyzer (MCP mode)")
    print(f"  URL: {url}\n")

    creatives, total_reported = scrape_creatives_via_cdp(
        url, cdp_url=args.cdp_url, max_scroll=args.max_scroll
    )

    if not creatives:
        print("\n  Nenhum criativo encontrado.")
        sys.exit(1)

    analysis = analyze(creatives, search_params, total_reported)
    print_report(analysis, creatives)
    report_path = save_report(analysis, creatives, search_params)

    print(f"  Use batch_download.py para baixar:")
    print(f"  python3 scripts/batch_download.py --report {report_path} --top 10\n")


if __name__ == "__main__":
    main()

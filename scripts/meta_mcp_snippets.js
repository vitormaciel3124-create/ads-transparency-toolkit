/**
 * MCP Snippets — Meta Ads Library (facebook.com/ads/library)
 *
 * JavaScript functions for Chrome DevTools MCP evaluate_script.
 * Copy/paste the function body into the MCP "function" parameter.
 *
 * Workflow:
 *   1. navigate_page → Meta Ads Library URL
 *   2. evaluate_script → dismissCookieConsent
 *   3. evaluate_script → scrollAndLoad (scroll progressivo)
 *   4. take_screenshot → verificar estado visual
 *   5. evaluate_script → extractAds (extrai tudo)
 *   6. Agente salva JSON em reports/ e apresenta ao usuário
 *   7. Para download: evaluate_script → getVideoUrlFromAdPage (em cada anúncio)
 */

// ─── SNIPPET 1: dismissCookieConsent ────────────────────────────────────────
// Dismiss the Facebook/Meta cookie consent banner if present.
// Run once right after navigate_page.

const dismissCookieConsent = `() => {
  const labels = [
    "Accept All", "Allow all cookies", "Accept all",
    "Aceitar tudo", "Alle akzeptieren", "Aceptar todo",
    "Tout accepter", "Decline optional cookies",
    "Allow essential and optional cookies"
  ];
  const buttons = [...document.querySelectorAll("button, [role='button']")];
  for (const label of labels) {
    const btn = buttons.find(b => (b.textContent || "").trim().startsWith(label));
    if (btn) { btn.click(); return { dismissed: true, label }; }
  }
  return { dismissed: false };
}`;


// ─── SNIPPET 2: scrollAndLoad ───────────────────────────────────────────────
// Scrolls progressively to load more ads. Returns stats.
// Parameters tunable via the constants at the top.

const scrollAndLoad = `async () => {
  const MAX_SCROLLS = 40;
  const SCROLL_DELAY = 900;
  const STALE_LIMIT = 6;

  let prevCount = 0;
  let staleRounds = 0;
  let scrollsDone = 0;

  const countVideos = () => document.querySelectorAll("video").length;

  for (let i = 0; i < MAX_SCROLLS; i++) {
    window.scrollBy(0, window.innerHeight * 0.8);
    await new Promise(r => setTimeout(r, SCROLL_DELAY));
    scrollsDone = i + 1;

    // Click "See more" / "Ver mais" buttons if present
    const seeMore = [...document.querySelectorAll("div[role='button'], button")]
      .find(b => /see more|ver mais|mehr anzeigen|voir plus/i.test(b.textContent || ""));
    if (seeMore) {
      try { seeMore.click(); await new Promise(r => setTimeout(r, 2000)); } catch {}
    }

    const count = countVideos();
    if (count > prevCount) {
      staleRounds = 0;
    } else {
      staleRounds++;
      if (staleRounds >= STALE_LIMIT) {
        return { videosLoaded: count, scrollsDone, stoppedReason: "stale" };
      }
    }
    prevCount = count;
  }

  return { videosLoaded: countVideos(), scrollsDone, stoppedReason: "maxScrolls" };
}`;


// ─── SNIPPET 3: extractAds ─────────────────────────────────────────────────
// Extracts all video ad data from the loaded page.
// Returns { total, ads: [...] }

const extractAds = `() => {
  const results = [];
  const seenUrls = new Set();
  const seenLibIds = new Set();

  const LIB_ID_RE = /(?:Library|Bibliotheks|Biblioteca|Médiathèque)\\s*ID[:\\s]+([0-9]{5,20})/i;
  const DATE_RE   = /(?:Started running on|Gestartet am|Começou a ser veiculado|Inicio de publicación)\\s*[:：]?\\s*(.+?)(?:\\n|$)/i;
  const STATUS_RE = /(?:Active|Inactive|Actif|Inactif|Ativo|Inativo|Aktiv|Inaktiv)/i;

  document.querySelectorAll("video").forEach(video => {
    const url = video.currentSrc || video.src || "";
    if (!url || url.startsWith("blob:") || url.startsWith("data:") || !url.startsWith("http")) return;
    if (seenUrls.has(url)) return;
    seenUrls.add(url);

    // Walk up to find the ad card container
    let el = video.parentElement;
    let cardEl = null;
    for (let depth = 0; depth < 35 && el; depth++) {
      if (LIB_ID_RE.test(el.innerText || "")) { cardEl = el; break; }
      el = el.parentElement;
    }

    let libraryId = null, advertiserName = null, startDate = null;
    let isActive = null, pageUrl = null;

    if (cardEl) {
      const text = cardEl.innerText || "";
      const libMatch  = text.match(LIB_ID_RE);
      const dateMatch = text.match(DATE_RE);
      const statMatch = text.match(STATUS_RE);

      libraryId = libMatch  ? libMatch[1]  : null;
      startDate = dateMatch ? dateMatch[1].trim() : null;
      isActive  = statMatch ? /active|actif|ativo|aktiv/i.test(statMatch[0]) : null;

      if (libraryId && seenLibIds.has(libraryId)) return;
      if (libraryId) seenLibIds.add(libraryId);

      // Advertiser name: first <a> linking to a Facebook page
      const links = Array.from(cardEl.querySelectorAll("a[href]"));
      for (const link of links) {
        const href = link.getAttribute("href") || "";
        if (href.includes("/ads/") || href.includes("/ad_library") || href.includes("?id=")) continue;
        if (!href.includes("facebook.com") && !href.startsWith("/")) continue;
        const name = (link.textContent || "").trim();
        if (name.length > 1 && name.length < 120) {
          advertiserName = name;
          pageUrl = href.startsWith("http") ? href : "https://www.facebook.com" + href;
          break;
        }
      }

      if (!advertiserName) {
        const img = cardEl.querySelector("img[alt]");
        if (img) advertiserName = (img.getAttribute("alt") || "").trim() || null;
      }
    }

    results.push({
      library_id:      libraryId,
      advertiser_name: advertiserName,
      advertiser_page: pageUrl,
      video_url:       url,
      start_date:      startDate,
      is_active:       isActive,
      ad_url:          libraryId ? "https://www.facebook.com/ads/library/?id=" + libraryId : null,
    });
  });

  return { total: results.length, ads: results };
}`;


// ─── SNIPPET 4: getPageStats ────────────────────────────────────────────────
// Quick stats without full extraction.

const getPageStats = `() => {
  const videos = document.querySelectorAll("video");
  const withSrc = [...videos].filter(v => {
    const u = v.currentSrc || v.src || "";
    return u.startsWith("http") && !u.startsWith("blob:");
  });
  return {
    totalVideos:    videos.length,
    videosWithSrc:  withSrc.length,
    scrollY:        Math.round(window.scrollY),
    bodyHeight:     document.body.scrollHeight,
    pageUrl:        window.location.href,
  };
}`;


// ─── SNIPPET 5: getVideoUrlFromAdPage ───────────────────────────────────────
// Run on an individual ad page (facebook.com/ads/library/?id=XXXXX).
// Waits for video to load, optionally tries HD, returns the CDN URL.
// Use after navigate_page to the ad's URL.

const getVideoUrlFromAdPage = `async () => {
  // Wait for video to appear
  for (let i = 0; i < 20; i++) {
    if (document.querySelector("video")) break;
    await new Promise(r => setTimeout(r, 500));
  }

  const video = document.querySelector("video");
  if (!video) return { ok: false, error: "no video element found" };

  // Play to trigger src loading
  try { video.muted = true; await video.play(); } catch {}
  await new Promise(r => setTimeout(r, 1500));

  const url = video.currentSrc || video.src || "";
  if (!url || url.startsWith("blob:") || url.startsWith("data:")) {
    // Check <source> tags
    const source = video.querySelector("source[src]");
    const srcUrl = source ? source.getAttribute("src") : null;
    if (srcUrl && srcUrl.startsWith("http")) {
      return { ok: true, video_url: srcUrl };
    }
    return { ok: false, error: "video src is blob/data/empty", raw: url || "(empty)" };
  }

  return { ok: true, video_url: url };
}`;


// ─── SNIPPET 6: tryHdAndGetUrl ──────────────────────────────────────────────
// Same as getVideoUrlFromAdPage but first tries to switch to HD quality.

const tryHdAndGetUrl = `async () => {
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
  function normText(el) { return (el.textContent || "").replace(/\\s+/g, " ").trim(); }
  function clickEl(el) {
    if (!el) return;
    try {
      el.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
      el.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      el.dispatchEvent(new PointerEvent("pointerup", { bubbles: true }));
      el.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
      el.click();
    } catch { try { el.click(); } catch {} }
  }

  // Wait for video
  for (let i = 0; i < 20; i++) {
    if (document.querySelector("video")) break;
    await sleep(500);
  }
  const video = document.querySelector("video");
  if (!video) return { ok: false, error: "no video element found" };

  try { video.muted = true; await video.play(); } catch {}
  await sleep(400);

  // Try HD: find settings gear near video
  const gearLabels = ["Definições", "Settings", "Ajustes", "Configurações", "Paramètres"];
  let gear = null, p = video.parentElement;
  for (let i = 0; i < 22 && p; i++) {
    for (const label of gearLabels) {
      const btn = p.querySelector('[role="button"][aria-label="' + label + '"]');
      if (btn) { gear = btn; break; }
    }
    if (gear) break;
    p = p.parentElement;
  }

  let hdResult = "gear_not_found";
  if (gear) {
    clickEl(gear);
    await sleep(500);

    // Click quality row
    const nodes = document.body.querySelectorAll('[role="menuitem"],[role="button"],div[tabindex="0"]');
    let qualityRow = null;
    for (const el of nodes) {
      if (/\\b(qualidade|quality)\\b/i.test(normText(el))) { qualityRow = el; break; }
    }

    if (qualityRow) {
      clickEl(qualityRow);
      await sleep(500);

      // Pick best quality
      const opts = document.body.querySelectorAll('[role="menuitem"],[role="option"],[role="menuitemcheckbox"],li');
      let best = null, bestScore = 0;
      for (const el of opts) {
        const t = normText(el).toLowerCase();
        let sc = 0;
        if (/1080/.test(t)) sc = 100;
        else if (/\\bhd\\b/.test(t)) sc = 90;
        else if (/alta|high|max|máx/.test(t)) sc = 80;
        else if (/720/.test(t)) sc = 70;
        if (sc > bestScore) { bestScore = sc; best = el; }
      }
      if (best) {
        clickEl(best);
        await sleep(800);
        hdResult = "hd_applied";
      } else {
        hdResult = "no_hd_option";
      }
    } else {
      hdResult = "quality_menu_not_found";
    }

    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await sleep(300);
  }

  await sleep(500);
  const url = video.currentSrc || video.src || "";
  if (!url || url.startsWith("blob:") || url.startsWith("data:")) {
    return { ok: false, error: "video src is blob/data/empty", hd: hdResult };
  }
  return { ok: true, video_url: url, hd: hdResult };
}`;


// ─── SNIPPET 7: selectAllAndGetUrls ─────────────────────────────────────────
// Collects ALL video URLs currently in the page (fast, no HD attempt).
// Useful for bulk export after scrollAndLoad.

const selectAllAndGetUrls = `() => {
  const urls = [];
  document.querySelectorAll("video").forEach(v => {
    const url = v.currentSrc || v.src || "";
    if (url && url.startsWith("http") && !url.startsWith("blob:")) {
      if (!urls.includes(url)) urls.push(url);
    }
  });
  return { total: urls.length, urls };
}`;


// Export for reference
if (typeof module !== "undefined") {
  module.exports = {
    dismissCookieConsent, scrollAndLoad, extractAds, getPageStats,
    getVideoUrlFromAdPage, tryHdAndGetUrl, selectAllAndGetUrls,
  };
}

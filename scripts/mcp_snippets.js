/**
 * MCP Snippets — JavaScript functions for Chrome DevTools MCP evaluate_script.
 *
 * Each exported snippet is designed to run inside the Ads Transparency Center
 * page via the MCP evaluate_script tool. Copy/paste the function body into
 * the "function" parameter.
 *
 * Usage from Cursor agent:
 *   CallMcpTool(server="user-chrome-devtools", toolName="evaluate_script",
 *               arguments={"function": "<snippet>"})
 */

// ─── SNIPPET 1: expandAndScroll ─────────────────────────────────────────────
// Clicks "See all ads", then scrolls to load creatives.
// Returns { totalLoaded, stoppedReason }
//
// Parameters (via closure defaults):
//   maxScrolls = 50  — maximum scroll iterations
//   scrollDelay = 1500 — ms between scrolls
//   staleLimit = 5   — stop after N scrolls with no new results

const expandAndScroll = `async () => {
  const MAX_SCROLLS = 50;
  const SCROLL_DELAY = 1500;
  const STALE_LIMIT = 5;

  // Click "See all ads" button if present
  const expandBtn = document.querySelector('material-button.grid-expansion-button');
  if (expandBtn) {
    expandBtn.click();
    await new Promise(r => setTimeout(r, 3000));
  }

  let prevCount = 0;
  let staleRounds = 0;
  let scrollsDone = 0;

  for (let i = 0; i < MAX_SCROLLS; i++) {
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, SCROLL_DELAY));

    // Click "Ver mais resultados" / "See more" if it appears mid-scroll
    const moreBtn = document.querySelector('material-button.search-improvements-see-more-button');
    if (moreBtn) {
      try { moreBtn.click(); await new Promise(r => setTimeout(r, 2000)); } catch(e) {}
    }

    const count = document.querySelectorAll("a[href*='/creative/']").length;
    scrollsDone = i + 1;

    if (count > prevCount) {
      staleRounds = 0;
    } else {
      staleRounds++;
      if (staleRounds >= STALE_LIMIT) {
        return { totalLoaded: count, scrollsDone, stoppedReason: 'stale' };
      }
    }
    prevCount = count;
  }

  return {
    totalLoaded: document.querySelectorAll("a[href*='/creative/']").length,
    scrollsDone,
    stoppedReason: 'maxScrolls'
  };
}`;


// ─── SNIPPET 2: extractCreatives ────────────────────────────────────────────
// Extracts all creative data from the currently loaded page.
// Returns { total, creatives: [{index, creative_id, advertiser_id, ...}] }

const extractCreatives = `() => {
  const cards = document.querySelectorAll('creative-preview');
  const creatives = [];
  const seen = new Set();

  cards.forEach((card, i) => {
    const link = card.querySelector("a[href*='/creative/']");
    if (!link) return;

    const href = link.href || link.getAttribute('href') || '';
    if (seen.has(href)) return;
    seen.add(href);

    const match = href.match(/advertiser\\/(AR\\w+)\\/creative\\/(CR\\w+)/);
    const nameEl = card.querySelector('.advertiser-name, [class*="advertiser-name"]');
    const verifiedEl = card.querySelector('.verified, [class*="verified"]');
    const iconLink = card.querySelector('a');
    const iconText = iconLink ? iconLink.textContent.trim().toLowerCase() : '';

    const formatMap = { videocam: 'video', image: 'image', text_snippet: 'text', web: 'web' };

    creatives.push({
      index: creatives.length + 1,
      creative_id: match ? match[2] : null,
      advertiser_id: match ? match[1] : null,
      advertiser_name: nameEl ? nameEl.textContent.trim() : null,
      url: href.startsWith('http') ? href : 'https://adstransparency.google.com' + href,
      format: formatMap[iconText] || 'video',
      verified: !!verifiedEl
    });
  });

  return { total: creatives.length, creatives };
}`;


// ─── SNIPPET 3: getPageStats ────────────────────────────────────────────────
// Quick stats about the current page state without extracting full data.

const getPageStats = `() => {
  const cards = document.querySelectorAll('creative-preview');
  const links = document.querySelectorAll("a[href*='/creative/']");

  // Try to get the reported total
  let totalReported = null;
  const allText = document.body.innerText;
  const match = allText.match(/(Cerca de |About )([\\d.,]+\\s*(mil|thousand|hundred)?\\s*(anúncios|ads))/i);
  if (match) totalReported = match[0];

  // Count unique advertisers
  const advertisers = new Set();
  links.forEach(a => {
    const m = a.href.match(/advertiser\\/(AR\\w+)/);
    if (m) advertisers.add(m[1]);
  });

  return {
    totalReported,
    cardsLoaded: cards.length,
    linksFound: links.length,
    uniqueAdvertisers: advertisers.size,
    pageUrl: window.location.href,
    scrollY: window.scrollY,
    bodyHeight: document.body.scrollHeight
  };
}`;


// ─── SNIPPET 4: extractVideoId ─────────────────────────────────────────────
// Run on an individual creative page to extract the YouTube video ID.
// NOTE: The YouTube embed iframe is inside cross-origin safeframes (3 levels deep),
// so direct DOM access doesn't work. Instead, use the MCP list_network_requests
// tool to find the youtube.com/embed/ request and extract the video ID from there.
//
// Workflow:
//   1. navigate_page -> creative URL
//   2. wait 6s for iframes to load
//   3. list_network_requests with resourceTypes: ["document"]
//   4. Find the request URL containing "youtube.com/embed/"
//   5. Extract video ID from the URL path
//
// This snippet provides a fallback that checks performance entries (works sometimes):

const extractVideoId = `async () => {
  await new Promise(r => setTimeout(r, 6000));

  // Method 1: Check performance resource timing entries
  const entries = performance.getEntriesByType('resource');
  const ytEntries = entries.filter(e => e.name.includes('youtube.com/embed/'));
  const videoIds = ytEntries.map(e => {
    const m = e.name.match(/\\/embed\\/([a-zA-Z0-9_-]+)/);
    return m ? m[1] : null;
  }).filter(Boolean);

  const unique = [...new Set(videoIds)];

  return {
    found: unique.length > 0,
    videoIds: unique,
    videos: unique.map(id => ({
      videoId: id,
      youtubeUrl: 'https://www.youtube.com/watch?v=' + id,
      shortsUrl: 'https://www.youtube.com/shorts/' + id
    })),
    pageUrl: window.location.href,
    hint: 'If empty, use list_network_requests to find youtube.com/embed/ URLs'
  };
}`;


// ─── SNIPPET 5: analyzeCreatives ────────────────────────────────────────────
// Full analysis: extract + stats (mirrors analyze.py logic).
// Run after expandAndScroll.

const analyzeCreatives = `() => {
  const cards = document.querySelectorAll('creative-preview');
  const creatives = [];
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

    creatives.push({
      creative_id: match ? match[2] : null,
      advertiser_id: match ? match[1] : null,
      advertiser_name: nameEl ? nameEl.textContent.trim() : null,
      url: href.startsWith('http') ? href : 'https://adstransparency.google.com' + href,
      verified: !!verifiedEl
    });
  });

  // Analysis
  const advertiserCount = {};
  const advertiserNames = {};
  const creativeIdCount = {};

  creatives.forEach(c => {
    const aid = c.advertiser_id || 'unknown';
    advertiserCount[aid] = (advertiserCount[aid] || 0) + 1;
    if (c.advertiser_name) advertiserNames[aid] = c.advertiser_name;
    if (c.creative_id) creativeIdCount[c.creative_id] = (creativeIdCount[c.creative_id] || 0) + 1;
  });

  const topAdvertisers = Object.entries(advertiserCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([id, count]) => ({ id, name: advertiserNames[id] || id, count }));

  const repeatedCreatives = Object.entries(creativeIdCount)
    .filter(([_, count]) => count > 1)
    .map(([id, count]) => ({ creative_id: id, occurrences: count }));

  const uniqueIds = new Set(creatives.map(c => c.creative_id).filter(Boolean));

  return {
    summary: {
      total_found: creatives.length,
      unique_creatives: uniqueIds.size,
      repeated_creatives: repeatedCreatives.length,
      advertisers_count: Object.keys(advertiserCount).length,
      verified_count: creatives.filter(c => c.verified).length
    },
    top_advertisers: topAdvertisers,
    repeated_creatives: repeatedCreatives,
    creatives
  };
}`;

// Export for reference (not used at runtime — snippets are copied to MCP calls)
if (typeof module !== 'undefined') {
  module.exports = { expandAndScroll, extractCreatives, getPageStats, extractVideoId, analyzeCreatives };
}

(() => {
  const STORAGE_KEY = "enabled";
  const LEDGER_PREFIX = "bilibiliShufflePlayed:";
  const ROOT_SELECTORS = [
    ".video-pod__list",
    ".video-pod",
    ".video-sections-content-list",
    ".video-sections-item-list",
    ".cur-list",
    ".ep-list",
    ".season-list",
    ".list-box",
    "#multi_page",
    ".multi-page",
    '[class*="video-pod"]',
    '[class*="playlist"]',
    '[class*="episode-list"]',
    '[class*="multi-page"]',
  ];
  const PLAYABLE_PATH = /^\/(?:video\/(?:BV[\w]+|av\d+)|bangumi\/play\/(?:ep\d+|ss\d+))/i;
  const boundVideos = new WeakSet();
  let enabled = false;
  let panel;
  let statusElement;
  let countElement;
  let nextButton;
  let lastUrl = location.href;
  let refreshTimer;

  function canonicalUrl(value) {
    try {
      const url = new URL(value, location.href);
      if (!PLAYABLE_PATH.test(url.pathname)) return null;
      const part = url.pathname.startsWith("/video/") ? url.searchParams.get("p") : null;
      return url.origin + url.pathname + (part ? "?p=" + encodeURIComponent(part) : "");
    } catch {
      return null;
    }
  }

  function currentUrl() {
    return canonicalUrl(location.href);
  }

  function isVisible(element) {
    if (!element?.isConnected) return false;
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
  }

  function titleFor(anchor) {
    return (anchor.getAttribute("title") || anchor.textContent || "").replace(/\s+/g, " ").trim();
  }

  function linksIn(root) {
    const unique = new Map();
    for (const anchor of root.querySelectorAll("a[href]")) {
      const url = canonicalUrl(anchor.href);
      if (url && !unique.has(url)) unique.set(url, { url, title: titleFor(anchor) });
    }
    return [...unique.values()];
  }

  function collectPlaylist() {
    const current = currentUrl();
    if (!current) return [];

    const candidates = new Set();
    for (const selector of ROOT_SELECTORS) {
      document.querySelectorAll(selector).forEach((element) => candidates.add(element));
    }

    // Include current-item ancestors because Bilibili changes playlist class names regularly.
    const currentAnchor = [...document.querySelectorAll("a[href]")].find((anchor) => canonicalUrl(anchor.href) === current);
    if (currentAnchor) {
      let ancestor = currentAnchor.parentElement;
      for (let depth = 0; ancestor && depth < 5; depth += 1, ancestor = ancestor.parentElement) {
        candidates.add(ancestor);
      }
    }

    let best = [];
    let bestScore = -1;
    for (const root of candidates) {
      if (!isVisible(root) ||
          root.closest("#reco_list, .recommend-list, .video-page-card") ||
          root.matches("#reco_list, .recommend-list, .video-page-card") ||
          root.querySelector("#reco_list, .recommend-list, .video-page-card")) continue;
      const links = linksIn(root);
      const semantic = /playlist|video-pod|episode|season|multi-page|ep-list|cur-list/i.test(root.className || "");
      if (links.length < 2 || links.length > (semantic ? 500 : 36) || !links.some((item) => item.url === current)) continue;
      const score = links.length + (semantic ? 20 : 0) + (root.matches("li, a") ? -3 : 0);
      if (score > bestScore) {
        best = links;
        bestScore = score;
      }
    }

    if (!best.some((item) => item.url === current)) best.unshift({ url: current, title: document.title });
    return best;
  }

  function makePanel() {
    if (panel?.isConnected) return;
    panel = document.createElement("section");
    panel.id = "bilibili-shuffle-panel";
    panel.setAttribute("aria-label", "Bilibili 乱序播放");
    panel.innerHTML = '<div class="shuffle-heading"><span>乱序播放</span><span class="shuffle-count"></span></div>' +
      '<p class="shuffle-status" role="status" aria-live="polite"></p>' +
      '<button class="shuffle-button" type="button">随机播放下一集</button>';
    document.documentElement.append(panel);
    statusElement = panel.querySelector(".shuffle-status");
    countElement = panel.querySelector(".shuffle-count");
    nextButton = panel.querySelector(".shuffle-button");
    nextButton.addEventListener("click", () => playNext(true));
  }

  function updatePanel() {
    if (!enabled) {
      panel?.remove();
      panel = null;
      return;
    }

    makePanel();
    const playlist = collectPlaylist();
    countElement.textContent = playlist.length > 1 ? playlist.length + " 个条目" : "";
    if (playlist.length > 1) {
      statusElement.textContent = "视频结束后会自动随机切换，也可以手动跳转。";
      nextButton.disabled = false;
    } else {
      statusElement.textContent = "当前页未找到可用的分 P、合集或选集列表。";
      nextButton.disabled = true;
    }
  }

  function ledgerFor(playlist) {
    const key = LEDGER_PREFIX + playlist.map((item) => item.url).sort().join("|");
    try {
      return { key, played: JSON.parse(sessionStorage.getItem(key) || "[]") };
    } catch {
      return { key, played: [] };
    }
  }

  function playNext(manual = false) {
    if (!enabled) return;
    const playlist = collectPlaylist();
    if (playlist.length < 2) {
      updatePanel();
      return;
    }

    const { key, played: previous } = ledgerFor(playlist);
    const current = currentUrl();
    const played = new Set(previous.filter((url) => playlist.some((item) => item.url === url)));
    if (current) played.add(current);

    let choices = playlist.filter((item) => !played.has(item.url));
    if (choices.length === 0) {
      played.clear();
      if (current) played.add(current);
      choices = playlist.filter((item) => item.url !== current);
    }

    const choice = choices[Math.floor(Math.random() * choices.length)];
    if (!choice) return;
    played.add(choice.url);
    try {
      sessionStorage.setItem(key, JSON.stringify([...played]));
    } catch {
      // Navigation still works if the browser blocks session storage.
    }
    if (manual) statusElement.textContent = "正在跳转：" + (choice.title || "随机条目");
    location.assign(choice.url);
  }

  function bindVideo(video) {
    if (boundVideos.has(video)) return;
    boundVideos.add(video);
    video.addEventListener("ended", () => {
      if (enabled) playNext(false);
    });
  }

  function refresh() {
    if (location.href !== lastUrl) lastUrl = location.href;
    if (enabled) updatePanel();
    document.querySelectorAll("video").forEach(bindVideo);
  }

  function scheduleRefresh() {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refresh, 180);
  }

  chrome.storage.local.get({ [STORAGE_KEY]: false }, (data) => {
    enabled = Boolean(data[STORAGE_KEY]);
    refresh();
  });

  chrome.storage.onChanged.addListener((changes, area) => {
    if (area === "local" && changes[STORAGE_KEY]) {
      enabled = Boolean(changes[STORAGE_KEY].newValue);
      refresh();
    }
  });

  chrome.runtime.onMessage.addListener((message) => {
    if (message?.type === "bilibili-shuffle:state") {
      enabled = Boolean(message.enabled);
      refresh();
    }
  });

  new MutationObserver((records) => {
    if (records.some((record) => !panel?.contains(record.target))) scheduleRefresh();
  }).observe(document.documentElement, { childList: true, subtree: true });
  window.addEventListener("popstate", scheduleRefresh);
  window.addEventListener("hashchange", scheduleRefresh);
  setInterval(() => {
    if (location.href !== lastUrl) scheduleRefresh();
  }, 900);
})();

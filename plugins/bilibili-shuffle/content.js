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
    "#playlist-video-action-list",
    ".action-list-inner",
    ".action-list",
    ".action-list-item-wrap[data-key]",
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
  let apiCacheKey = "";
  let apiPlaylist = [];
  let apiPlaylistTitle = "";
  let apiFetchingKey = "";
  let apiPlaylistTotal = 0;
  let apiPlaylistTruncated = false;

  function canonicalUrl(value) {
    try {
      const url = new URL(value, location.href);
      const hostname = url.hostname.toLowerCase();
      if (hostname !== "bilibili.com" &&
          !hostname.endsWith(".bilibili.com") &&
          hostname !== "bilibili.tv" &&
          !hostname.endsWith(".bilibili.tv")) return null;
      const listMatch = url.pathname.match(/^\/list\/(\d+)\/?$/);
      if (listMatch) {
        const videoId = url.searchParams.get("bvid");
        if (!videoId) return null;
        return creatorListUrl(
          url.origin,
          listMatch[1],
          videoId,
          url.searchParams.get("oid") || "",
          url.searchParams.get("sort_field") || "",
        );
      }
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

  function creatorListUrl(origin, listId, videoId, aid, sortField) {
    const query = new URLSearchParams();
    if (sortField) query.set("sort_field", sortField);
    if (aid) query.set("oid", aid);
    query.set("bvid", videoId);
    return origin + "/list/" + listId + "?" + query.toString();
  }

  function currentVideoId() {
    return location.pathname.match(/^\/video\/(BV[\w]+|av\d+)/i)?.[1] || "";
  }

  function creatorListInfo() {
    const match = location.pathname.match(/^\/list\/(\d+)\/?$/);
    if (!match) return null;
    const sortField = new URL(location.href).searchParams.get("sort_field") || "";
    return { listId: match[1], sortField, key: "space:" + match[1] + ":" + sortField };
  }

  function currentPlaylistKey() {
    return creatorListInfo()?.key || currentVideoId();
  }

  function isVisible(element) {
    if (!element?.isConnected) return false;
    const style = getComputedStyle(element);
    return style.display !== "none" && style.visibility !== "hidden" && element.getClientRects().length > 0;
  }

  function titleFor(anchor) {
    return (anchor.getAttribute("title") || anchor.textContent || "").replace(/\s+/g, " ").trim();
  }

  function listItemUrl(item) {
    const videoId = item.dataset.key || "";
    if (!/^(?:BV[\w]+|av\d+)$/i.test(videoId)) return null;
    const listMatch = location.pathname.match(/^\/list\/(\d+)\/?$/);
    if (!listMatch) return canonicalUrl("https://www.bilibili.com/video/" + videoId);

    const aid = (item.dataset.index || "").split("_").pop();
    return creatorListUrl(
      location.origin,
      listMatch[1],
      videoId,
      /^\d+$/.test(aid) ? aid : "",
      new URL(location.href).searchParams.get("sort_field") || "",
    );
  }

  function linksIn(root) {
    const unique = new Map();
    for (const anchor of root.querySelectorAll("a[href]")) {
      const url = canonicalUrl(anchor.href);
      if (url && !unique.has(url)) unique.set(url, { url, title: titleFor(anchor) });
    }

    const listItems = [];
    if (root.matches?.(".action-list-item-wrap[data-key]")) listItems.push(root);
    listItems.push(...root.querySelectorAll(".action-list-item-wrap[data-key], [data-index][data-key]"));
    for (const item of listItems) {
      const url = listItemUrl(item);
      if (!url || unique.has(url)) continue;
      const title = item.querySelector(".title");
      unique.set(url, {
        url,
        title: title?.getAttribute("title") || title?.textContent?.trim() || "",
      });
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
    const currentItem = [...document.querySelectorAll(".action-list-item-wrap[data-key], [data-index][data-key]")]
      .find((item) => listItemUrl(item) === current);
    const currentAnchor = [...document.querySelectorAll("a[href]")].find((anchor) => canonicalUrl(anchor.href) === current);
    const currentNode = currentItem || currentAnchor;
    if (currentNode) {
      let ancestor = currentNode.parentElement;
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
      const semantic = /playlist|action-list|video-pod|episode|season|multi-page|ep-list|cur-list/i
        .test((root.className || "") + " " + (root.id || ""));
      if (links.length < 2 || links.length > (semantic ? 1000 : 36) || !links.some((item) => item.url === current)) continue;
      const score = links.length + (semantic ? 20 : 0) + (root.matches("li, a") ? -3 : 0);
      if (score > bestScore) {
        best = links;
        bestScore = score;
      }
    }

    if (!best.some((item) => item.url === current)) best.unshift({ url: current, title: document.title });
    return best;
  }

  function requestApiPlaylist() {
    const creatorList = creatorListInfo();
    if (creatorList) {
      const { listId, sortField, key } = creatorList;
      if (apiCacheKey === key || apiFetchingKey === key) return;

      const storageKey = "bilibiliShuffleListCache:" + key;
      try {
        const cached = JSON.parse(sessionStorage.getItem(storageKey) || "null");
        if (cached && Array.isArray(cached.items)) {
          const unique = new Map();
          for (const item of cached.items) {
            const url = canonicalUrl(item.url);
            if (url && !unique.has(url)) unique.set(url, { url, title: String(item.title || "") });
          }
          if (unique.size > 1) {
            apiCacheKey = key;
            apiPlaylist = [...unique.values()];
            apiPlaylistTitle = "";
            apiPlaylistTotal = Number(cached.totalCount) || apiPlaylist.length;
            apiPlaylistTruncated = Boolean(cached.truncated);
            updatePanel();
            return;
          }
        }
      } catch {
        // Ignore stale session data and request a fresh list.
      }

      apiFetchingKey = key;
      chrome.runtime.sendMessage(
        { type: "bilibili-shuffle:get-creator-list", listId, sortField },
        (response) => {
          if (apiFetchingKey === key) apiFetchingKey = "";
          if (creatorListInfo()?.key !== key) return;
          apiCacheKey = key;

          if (!response?.ok || !Array.isArray(response.items)) {
            apiPlaylist = [];
            apiPlaylistTitle = "";
            apiPlaylistTotal = 0;
            apiPlaylistTruncated = false;
            updatePanel();
            return;
          }

          const unique = new Map();
          for (const item of response.items) {
            const url = canonicalUrl(item.url);
            if (url && !unique.has(url)) unique.set(url, { url, title: item.title || "" });
          }
          apiPlaylist = [...unique.values()];
          apiPlaylistTitle = "";
          apiPlaylistTotal = Number(response.totalCount) || apiPlaylist.length;
          apiPlaylistTruncated = Boolean(response.truncated);
          try {
            sessionStorage.setItem(storageKey, JSON.stringify({
              items: apiPlaylist,
              totalCount: apiPlaylistTotal,
              truncated: apiPlaylistTruncated,
            }));
          } catch {
            // Keep the in-memory list if session storage is full.
          }
          updatePanel();
        },
      );
      return;
    }

    const videoId = currentVideoId();
    if (!videoId || apiCacheKey === videoId || apiFetchingKey === videoId) return;

    apiFetchingKey = videoId;
    chrome.runtime.sendMessage({ type: "bilibili-shuffle:get-video-list", videoId }, (response) => {
      if (apiFetchingKey === videoId) apiFetchingKey = "";
      if (currentVideoId().toLowerCase() !== videoId.toLowerCase()) return;
      apiCacheKey = videoId;

      if (!response?.ok || !Array.isArray(response.items)) {
        apiPlaylist = [];
        apiPlaylistTitle = "";
        apiPlaylistTotal = 0;
        apiPlaylistTruncated = false;
        updatePanel();
        return;
      }

      const current = currentUrl();
      const unique = new Map();
      for (const item of response.items) {
        const url = String(item.aid || "") === String(response.currentAid || "")
          ? current
          : canonicalUrl(item.url);
        if (url && !unique.has(url)) unique.set(url, { url, title: item.title || "" });
      }
      apiPlaylist = [...unique.values()];
      apiPlaylistTitle = response.title || "";
      apiPlaylistTotal = apiPlaylist.length;
      apiPlaylistTruncated = false;
      updatePanel();
    });
  }

  function activePlaylist() {
    const playlistKey = currentPlaylistKey();
    return playlistKey && playlistKey.toLowerCase() === apiCacheKey.toLowerCase() && apiPlaylist.length > 1
      ? apiPlaylist
      : collectPlaylist();
  }

  function makePanel() {
    if (panel?.isConnected) return;
    panel = document.createElement("section");
    panel.id = "bilibili-shuffle-panel";
    panel.setAttribute("aria-label", "Bilibili 乱序播放");
    panel.innerHTML = '<div class="shuffle-heading"><span>乱序播放</span><span class="shuffle-count"></span></div>' +
      '<p class="shuffle-status" role="status" aria-live="polite"></p>' +
      '<button class="shuffle-button" type="button">随机播放下一条</button>';
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
    const playlistKey = currentPlaylistKey();
    const apiReady = playlistKey && playlistKey.toLowerCase() === apiCacheKey.toLowerCase() && apiPlaylist.length > 1;
    const playlist = activePlaylist();
    if (playlistKey && playlistKey.toLowerCase() === apiFetchingKey.toLowerCase() && !apiReady) {
      statusElement.textContent = creatorListInfo()
        ? "正在读取完整播单…"
        : "正在读取合集和分 P 列表…";
      countElement.textContent = "";
      nextButton.disabled = true;
      return;
    }
    countElement.textContent = playlist.length > 1
      ? (apiReady && apiPlaylistTruncated ? playlist.length + " / " + apiPlaylistTotal : playlist.length) + " 个条目"
      : "";
    if (playlist.length > 1) {
      const label = apiReady && apiPlaylistTitle ? apiPlaylistTitle + " · " : "";
      const range = apiReady && apiPlaylistTruncated
        ? "已加载 " + playlist.length + " / " + apiPlaylistTotal + " 条，"
        : "";
      statusElement.textContent = label + range + "视频结束后会自动随机切换，也可以手动跳转。";
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
    const playlist = activePlaylist();
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
    if (enabled) requestApiPlaylist();
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

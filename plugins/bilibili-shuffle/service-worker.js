chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "bilibili-shuffle:get-video-list") return undefined;

  const videoId = String(message.videoId || "");
  if (!/^(?:BV[\w]+|av\d+)$/i.test(videoId)) {
    sendResponse({ ok: false, error: "Invalid video id" });
    return undefined;
  }

  const query = /^av/i.test(videoId)
    ? "aid=" + encodeURIComponent(videoId.slice(2))
    : "bvid=" + encodeURIComponent(videoId);

  fetch("https://api.bilibili.com/x/web-interface/view?" + query)
    .then((response) => {
      if (!response.ok) throw new Error("Bilibili API returned " + response.status);
      return response.json();
    })
    .then((payload) => {
      if (payload.code !== 0 || !payload.data) {
        throw new Error(payload.message || "Bilibili did not return video data");
      }

      const data = payload.data;
      const episodes = (data.ugc_season?.sections || []).flatMap((section) =>
        (section.episodes || []).map((episode) => {
          const aid = String(episode.aid || episode.arc?.aid || "");
          const bvid = episode.bvid || episode.arc?.bvid || (aid ? "av" + aid : "");
          return {
            url: bvid ? "https://www.bilibili.com/video/" + bvid : "",
            title: episode.title || episode.arc?.title || "",
            aid,
          };
        }),
      ).filter((episode) => episode.url);

      if (episodes.length > 1) {
        sendResponse({
          ok: true,
          kind: "season",
          title: data.ugc_season.title || "",
          currentAid: String(data.aid || ""),
          items: episodes,
        });
        return;
      }

      const pages = data.pages || [];
      if (pages.length > 1) {
        const bvid = data.bvid || videoId;
        sendResponse({
          ok: true,
          kind: "pages",
          currentAid: String(data.aid || ""),
          items: pages.map((page) => ({
            url: "https://www.bilibili.com/video/" + bvid + (page.page > 1 ? "?p=" + page.page : ""),
            title: page.part || data.title || "",
            page: page.page,
          })),
        });
        return;
      }

      sendResponse({ ok: true, kind: "none", items: [] });
    })
    .catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== "bilibili-shuffle:get-creator-list") return undefined;

  const listId = String(message.listId || "");
  if (!/^\d+$/.test(listId)) {
    sendResponse({ ok: false, error: "Invalid creator list id" });
    return undefined;
  }

  const sortFields = { pubtime: 1, play: 2, fav: 3, list_play: 4 };
  const sortField = sortFields[String(message.sortField || "").toLowerCase()] || 1;
  const maximumItems = 2000;
  const pageSize = 100;

  (async () => {
    const items = new Map();
    let totalCount = 0;
    let cursor = null;
    let hasMore = true;
    let truncated = false;

    for (let page = 0; hasMore && page < Math.ceil(maximumItems / (pageSize - 1)) + 1; page += 1) {
      const params = new URLSearchParams({
        type: "1",
        biz_id: listId,
        ps: String(pageSize),
        desc: "true",
        sort_field: String(sortField),
        tid: "0",
      });
      if (cursor) {
        params.set("bvid", cursor.bvid);
        params.set("oid", cursor.oid);
        params.set("otype", "2");
        params.set("direction", "false");
      }

      const response = await fetch("https://api.bilibili.com/x/v2/medialist/resource/list?" + params);
      if (!response.ok) throw new Error("Bilibili list API returned " + response.status);
      const payload = await response.json();
      if (payload.code !== 0 || !payload.data) {
        throw new Error(payload.message || "Bilibili did not return creator list data");
      }

      const data = payload.data;
      totalCount = Number(data.total_count) || totalCount;
      const entries = data.media_list || [];
      for (const entry of entries) {
        const bvid = entry.bv_id || "";
        const aid = String(entry.id || "");
        if (!bvid || !aid || items.has(bvid) || items.size >= maximumItems) continue;
        const query = new URLSearchParams();
        if (message.sortField) query.set("sort_field", String(message.sortField));
        query.set("oid", aid);
        query.set("bvid", bvid);
        items.set(bvid, {
          url: "https://www.bilibili.com/list/" + listId + "?" + query.toString(),
          title: entry.title || "",
        });
      }

      const last = entries[entries.length - 1];
      hasMore = Boolean(data.has_more) && entries.length > 1;
      if (items.size >= maximumItems) {
        truncated = hasMore;
        break;
      }
      if (!hasMore || !last?.bv_id || !last?.id) break;
      if (cursor?.bvid === last.bv_id) break;
      cursor = { bvid: last.bv_id, oid: String(last.id) };
    }

    sendResponse({
      ok: true,
      items: [...items.values()],
      totalCount,
      truncated: truncated || hasMore,
    });
  })().catch((error) => sendResponse({ ok: false, error: error.message }));

  return true;
});

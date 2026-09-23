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

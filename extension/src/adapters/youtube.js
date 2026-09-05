/*
 * YouTube adapter.
 *
 * "Watching" is the interesting signal here, so dwell is the main event: sitting
 * on a video (/watch) or a short (/shorts) past a threshold sends what you're
 * watching, with the thumbnail. Likes are keyed on the like button's aria-label.
 *
 * YouTube is a single-page app that swaps videos without a full load, so the
 * dwell key is the video id from the URL and resets when it changes.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "youtube";

  function videoId() {
    const u = new URL(location.href);
    if (u.pathname === "/watch") return u.searchParams.get("v");
    const m = u.pathname.match(/\/shorts\/([^/]+)/);
    return m ? m[1] : null;
  }

  function nounForPath() {
    return /\/shorts\//.test(location.pathname) ? "a short" : "a video";
  }

  function context() {
    const id = videoId();
    const title =
      document.querySelector("h1.ytd-watch-metadata")?.innerText?.trim() ||
      document.querySelector('meta[name="title"]')?.content ||
      document.title.replace(/ - YouTube$/, "");
    const channel = document.querySelector("ytd-channel-name a")?.innerText?.trim();
    return {
      noun: nounForPath(),
      title,
      author: channel,
      url: id ? `https://www.youtube.com/watch?v=${id}` : location.href,
      image: id ? `https://i.ytimg.com/vi/${id}/hqdefault.jpg` : undefined,
    };
  }

  function init(base) {
    base.onClick((el) => {
      const b = el.closest('[aria-label]');
      if (!b) return;
      const label = (b.getAttribute("aria-label") || "").toLowerCase();
      let action = null;
      // "like this video along with N other people" / "Unlike"
      if (/^like this video|^like\b/.test(label)) action = "like";
      else if (/^unlike\b/.test(label)) action = "unlike";
      if (!action) return;
      base.once(`${action}:${videoId()}`, 2500, () =>
        base.emit(SITE, action, context()));
    });

    base.watchDwell(
      () => {
        const id = videoId();
        return id ? { site: SITE, key: id } : null;
      },
      { seconds: 90, noun: nounForPath(), detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

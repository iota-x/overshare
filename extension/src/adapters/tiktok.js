/*
 * TikTok adapter.
 *
 * TikTok tags its controls with `data-e2e` and aria-labels ("like",
 * "Follow"). Videos live at /@user/video/<id>. Watching is the main signal:
 * lingering on a video is the "lost in TikTok" case.
 *
 * NOT YET tuned against a live session — data-e2e values are TikTok's to change.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "tiktok";

  function videoId() {
    const m = location.pathname.match(/\/video\/(\d+)/);
    return m ? m[1] : null;
  }

  function context() {
    const author = document.querySelector('[data-e2e="browse-username"], [data-e2e="video-author-uniqueid"]')
      ?.innerText?.trim();
    const desc = document.querySelector('[data-e2e="browse-video-desc"], [data-e2e="video-desc"]')
      ?.innerText?.trim();
    return { noun: "a video", url: location.href, author, text: desc };
  }

  function init(base) {
    base.onClick((el) => {
      const like = el.closest('[data-e2e="like-icon"], [data-e2e="browse-like-icon"]');
      if (like) {
        const on = base.pressed(like);   // true if it was already liked
        const action = on ? "unlike" : "like";
        base.once(`${action}:${location.href}`, 2500, () => base.emit(SITE, action, context()));
        return;
      }
      const label = (el.closest('[aria-label]')?.getAttribute("aria-label") || "").toLowerCase();
      if (/^follow\b/.test(label)) {
        base.once(`follow:${location.href}`, 2500, () => base.emit(SITE, "follow", context()));
      } else if (/save|favorite/.test(label)) {
        base.once(`save:${location.href}`, 2500, () => base.emit(SITE, "save", context()));
      }
    });

    base.watchDwell(
      () => {
        const id = videoId();
        return id ? { site: SITE, key: id } : null;
      },
      { seconds: 60, noun: "a video", detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

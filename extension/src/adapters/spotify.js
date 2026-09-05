/*
 * Spotify (web player) adapter.
 *
 * The one action worth catching is saving a track (the heart). Spotify labels
 * it "Save to Your Library" / "Remove from Your Library". Dwell = listening: a
 * long sit on one album/playlist/track page.
 *
 * NOT YET tuned against a live session.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "spotify";

  function context() {
    const title = document.querySelector('meta[property="og:title"]')?.content
      || document.title.replace(/ [-|] Spotify.*$/, "");
    return { noun: "a track", url: location.href, title };
  }

  function init(base) {
    base.onClick((el) => {
      const b = el.closest('[aria-label]');
      if (!b) return;
      const label = (b.getAttribute("aria-label") || "").toLowerCase();
      if (/save to your library|add to your library/.test(label)) {
        base.once(`save:${location.href}`, 2500, () => base.emit(SITE, "save", context()));
      }
    });

    base.watchDwell(
      () => {
        const m = location.pathname.match(/\/(album|playlist|track|artist)\/([^/]+)/);
        return m ? { site: SITE, key: m[2] } : null;
      },
      { seconds: 120, noun: "music", detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

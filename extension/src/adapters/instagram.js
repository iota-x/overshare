/*
 * Instagram adapter.
 *
 * Instagram gives its icons `aria-label`s ("Like", "Unlike", "Save", "Remove")
 * and little else stable, so this keys on those. Posts live at /p/<id>/, reels
 * at /reel/<id>/ or /reels/<id>/ — the "liked a reel" case is just a like whose
 * page is a reel, so the noun is chosen from the URL.
 *
 * Detected: like / unlike, save, follow, and dwell on a post or reel.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "instagram";

  function nounForPath(p = location.pathname) {
    if (/\/reels?\//.test(p)) return "a reel";
    if (/\/p\//.test(p)) return "a post";
    if (/\/stories\//.test(p)) return "a story";
    return "something";
  }

  function context() {
    // IG rarely exposes the caption near the button reliably; send the page and
    // a thumbnail, which is what reads well anyway.
    const og = document.querySelector('meta[property="og:image"]')?.content;
    const desc = document.querySelector('meta[property="og:title"]')?.content;
    return { noun: nounForPath(), url: location.href, image: og, text: desc };
  }

  function labelOf(el) {
    const b = el.closest('[aria-label]');
    return b ? (b.getAttribute("aria-label") || "").toLowerCase() : "";
  }

  function init(base) {
    base.onClick((el) => {
      if (base.looksLikeDM()) return;   // never the DM screen
      const label = labelOf(el);
      let action = null;
      if (label === "like") action = "like";
      else if (label === "unlike") action = "unlike";
      else if (label === "save") action = "save";
      else if (/^follow\b/.test(label)) action = "follow";
      if (!action) return;
      base.once(`${action}:${location.href}`, 2500, () =>
        base.emit(SITE, action, context()));
    });

    base.watchDwell(
      () => {
        const m = location.pathname.match(/\/(reels?|p)\/([^/]+)/);
        if (!m) return null;
        return { site: SITE, key: m[2] };
      },
      { seconds: 45, noun: nounForPath(), detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

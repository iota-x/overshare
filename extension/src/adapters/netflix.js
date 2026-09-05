/*
 * Netflix adapter.
 *
 * Netflix has no public "like" worth catching (thumbs live behind a menu), so
 * this is watching only: lingering on a title's page, or sitting in the player.
 * Dwell keyed on the title id (/title/<id> or /watch/<id>).
 *
 * NOT YET tuned against a live session.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "netflix";

  function titleId() {
    const m = location.pathname.match(/\/(?:watch|title)\/(\d+)/);
    return m ? m[1] : null;
  }

  function context() {
    const name = document.querySelector('.video-title, .previewModal--section-header, h1')?.innerText?.trim()
      || document.title.replace(/ [-|] Netflix.*$/, "");
    return { noun: "something", title: name, url: location.href };
  }

  function init(base) {
    base.watchDwell(
      () => {
        const id = titleId();
        return id ? { site: SITE, key: id } : null;
      },
      { seconds: 90, noun: "something", detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

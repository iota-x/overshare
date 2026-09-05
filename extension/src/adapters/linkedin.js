/*
 * LinkedIn adapter.
 *
 * The feed's reaction button is labelled "React Like" (and toggles). This
 * catches likes and lingering on a single post (/feed/update/… or /posts/…).
 *
 * NOT YET tuned against a live session.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "linkedin";

  function context() {
    return { noun: "a post", url: location.href };
  }

  function init(base) {
    base.onClick((el) => {
      const b = el.closest('[aria-label]');
      if (!b) return;
      const label = (b.getAttribute("aria-label") || "").toLowerCase();
      if (/react like|^like\b/.test(label)) {
        const on = base.pressed(b);
        const action = on ? "unlike" : "like";
        base.once(`${action}:${Date.now()}`, 2500, () => base.emit(SITE, action, context()));
      }
    });

    base.watchDwell(
      () => {
        const m = location.pathname.match(/\/(?:posts|feed\/update)\/([^/?#]+)/);
        return m ? { site: SITE, key: m[1] } : null;
      },
      { seconds: 60, noun: "a post", detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

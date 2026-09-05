/*
 * Content-script entry. Loaded last, after base.js and the one adapter the
 * manifest matched for this host. Its only job is to start that adapter.
 *
 * Each adapter registers itself as window.__overshare.adapter during its own
 * load; this calls its init() once the page is ready. Kept trivial so the
 * per-site logic all lives in the adapter, and adding a site never touches this.
 */

(function () {
  const NS = window.__overshare;
  if (!NS || !NS.adapter || NS.started) return;
  NS.started = true;

  const start = () => {
    try {
      NS.adapter.init(NS.base);
    } catch (e) {
      console.warn("[overshare] adapter failed to start:", e);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();

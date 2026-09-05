/*
 * Shared machinery every site adapter builds on.
 *
 * Loaded before each adapter in the same content-script world, so an adapter is
 * just: watch the page, and call `Overshare.emit(...)` when something happens.
 * Everything hard — sending, dwell timing, click delegation, not firing twice —
 * lives here, once.
 *
 * Nothing here decides whether an event is *allowed*; that is the background's
 * job, against the toggles. An adapter emits freely and the gate is elsewhere.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  if (NS.base) return;   // a re-injection (SPA navigations) must not re-wrap

  /** Send one detected event to the background, which decides + delivers. */
  function emit(site, action, detail = {}) {
    try {
      chrome.runtime.sendMessage({
        type: "overshare-event",
        event: { site, action, url: location.href, ...detail },
      });
    } catch {
      /* extension context torn down (update/reload) — nothing to do */
    }
  }

  /**
   * Fire `fn` at most once per `key` per `windowMs`. Sites re-render, so the
   * same like button can surface several click/DOM events in a blink; without
   * this the partner would get three "liked" cards for one tap.
   */
  const _seen = new Map();
  function once(key, windowMs, fn) {
    const now = Date.now();
    const last = _seen.get(key) || 0;
    if (now - last < windowMs) return;
    _seen.set(key, now);
    // keep the map from growing forever on a long session
    if (_seen.size > 500) {
      for (const [k, t] of _seen) if (now - t > 60000) _seen.delete(k);
    }
    fn();
  }

  /**
   * Delegated click watcher. Adapters describe the control they care about with
   * a test on the clicked element's ancestor chain; this handles the listener,
   * the closest() walk, and the de-dupe. Runs on capture so it still sees the
   * click when the site stops propagation.
   */
  function onClick(matchFn) {
    document.addEventListener(
      "click",
      (e) => {
        const el = e.target instanceof Element ? e.target : null;
        if (!el) return;
        try { matchFn(el, e); } catch { /* one bad match must not kill the rest */ }
      },
      true,
    );
  }

  /** aria-pressed / aria-label helpers — how most of these buttons expose state. */
  function pressed(el) {
    const btn = el.closest('[aria-pressed],[aria-checked]');
    if (!btn) return null;
    const v = btn.getAttribute("aria-pressed") ?? btn.getAttribute("aria-checked");
    return v === "true";
  }

  /**
   * Dwell: tell the background when the viewer has sat on the SAME thing for a
   * while. "The same thing" is keyed by whatever the adapter calls the current
   * item (a post id, or just the URL). Fires once per item; resets when the item
   * changes. Only counts foreground time — a backgrounded tab doesn't linger.
   */
  function watchDwell(getItem, { seconds = 60, noun = "this", detail = () => ({}) } = {}) {
    let key = null;
    let since = 0;
    let fired = false;

    function tick() {
      if (document.hidden) { return; }
      const item = getItem();
      if (!item) { key = null; fired = false; return; }
      if (item.key !== key) {
        key = item.key;
        since = Date.now();
        fired = false;
        return;
      }
      if (!fired && Date.now() - since >= seconds * 1000) {
        fired = true;
        const minutes = Math.round((Date.now() - since) / 60000);
        emit(item.site, "dwell", { noun, minutes, ...detail(item) });
      }
    }

    setInterval(tick, 5000);
    document.addEventListener("visibilitychange", () => { if (document.hidden) since = Date.now(); });
  }

  /** Is the viewer on a DM / messages screen? Adapters use this with quietDms. */
  function looksLikeDM() {
    return /\/(messages|direct|dm)(\/|$)/i.test(location.pathname);
  }

  NS.base = { emit, once, onClick, pressed, watchDwell, looksLikeDM };
})();

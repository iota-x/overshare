/*
 * Reddit adapter.
 *
 * Reddit's current UI is web components (shreddit-*) whose vote buttons carry
 * aria-labels ("upvote" / "downvote") and toggle aria-pressed. This keys on
 * those. Posts live at /r/<sub>/comments/<id>/…, which also gives the subreddit.
 *
 * Detected: upvote, downvote, save, and dwell on a post/comments page.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "reddit";

  function postInfo() {
    const m = location.pathname.match(/\/r\/([^/]+)\/comments\/([^/]+)(?:\/([^/]+))?/);
    if (!m) return null;
    const sub = `r/${m[1]}`;
    const slug = (m[3] || "").replace(/-/g, " ").trim();
    const title =
      document.querySelector("shreddit-post")?.getAttribute("post-title") ||
      document.querySelector('h1[slot="title"], h1')?.innerText?.trim() ||
      (slug ? slug.charAt(0).toUpperCase() + slug.slice(1) : undefined);
    return { id: m[2], sub, title };
  }

  function context() {
    const info = postInfo();
    return {
      noun: "a post",
      title: info?.title,
      author: info?.sub,
      url: location.href,
    };
  }

  function init(base) {
    base.onClick((el) => {
      const b = el.closest('[aria-label],button');
      if (!b) return;
      const label = (b.getAttribute("aria-label") || b.innerText || "").toLowerCase();
      let action = null;
      if (/upvote/.test(label)) action = "upvote";
      else if (/downvote/.test(label)) action = "downvote";
      else if (/^save\b/.test(label)) action = "save";
      if (!action) return;
      base.once(`${action}:${location.href}`, 2500, () =>
        base.emit(SITE, action, context()));
    });

    base.watchDwell(
      () => {
        const info = postInfo();
        return info ? { site: SITE, key: info.id } : null;
      },
      { seconds: 60, noun: "a post", detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

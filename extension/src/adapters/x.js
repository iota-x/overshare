/*
 * X / Twitter adapter.
 *
 * X marks its controls with stable-ish `data-testid`s, which is what this keys
 * on — far steadier than class names, though still X's to change without notice.
 * Every selector lives here so a break is one file to fix.
 *
 * Detected: like / unlike, repost, reply, follow, "Not interested in this post",
 * and dwell on a single tweet's page.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "x";

  // Everything site-specific, in one spot.
  const SEL = {
    tweet: 'article[data-testid="tweet"]',
    text: '[data-testid="tweetText"]',
    like: '[data-testid="like"]',        // present when NOT yet liked
    unlike: '[data-testid="unlike"]',    // present when already liked
    repost: '[data-testid="retweet"]',
    reply: '[data-testid="reply"]',
    follow: '[data-testid$="-follow"]',
    image: '[data-testid="tweetPhoto"] img',
    timeLink: 'a[href*="/status/"] time',
  };

  // Pull the post's text/author/url/image out of the article a control sits in.
  function context(fromEl) {
    const art = fromEl.closest(SEL.tweet);
    if (!art) return {};
    const text = art.querySelector(SEL.text)?.innerText?.trim();
    const img = art.querySelector(SEL.image)?.src;
    const timeLink = art.querySelector(SEL.timeLink)?.closest("a")?.href;
    // The first user link in the header is the author handle.
    const author = art.querySelector('[data-testid="User-Name"] a[href^="/"]')
      ?.getAttribute("href")?.replace(/^\//, "@");
    return {
      noun: "a post",
      text,
      url: timeLink || location.href,
      image: img,
      author,
    };
  }

  function init(base) {
    // Likes, reposts, replies, follows — one delegated click watcher.
    base.onClick((el) => {
      const hit = (sel) => el.closest(sel);
      let action = null;
      let anchor = null;
      if ((anchor = hit(SEL.like)))       action = "like";
      else if ((anchor = hit(SEL.unlike))) action = "unlike";
      else if ((anchor = hit(SEL.repost))) action = "repost";
      else if ((anchor = hit(SEL.reply)))  action = "reply";
      else if ((anchor = hit(SEL.follow))) action = "follow";
      if (!action) return;

      const ctx = context(anchor);
      const key = `${action}:${ctx.url || Math.random()}`;
      base.once(key, 2500, () => base.emit(SITE, action, ctx));
    });

    // "Not interested in this post" — a menu item that appears after the caret.
    base.onClick((el) => {
      const item = el.closest('[role="menuitem"]');
      if (!item) return;
      const label = (item.innerText || "").toLowerCase();
      if (!label.includes("not interested")) return;
      base.once(`ni:${Date.now()}`, 2500, () =>
        base.emit(SITE, "not_interested", { noun: "a post" }));
    });

    // Dwell — only on a single tweet's page (…/status/123), the thing you sit
    // with. The timeline scrolling past is not "lingering on" anything.
    base.watchDwell(
      () => {
        const m = location.pathname.match(/\/status\/(\d+)/);
        if (!m) return null;
        return { site: SITE, key: m[1] };
      },
      {
        seconds: 60,
        noun: "a post",
        detail: () => {
          const art = document.querySelector(SEL.tweet);
          return art ? context(art.querySelector(SEL.like) || art) : {};
        },
      },
    );
  }

  NS.adapter = { init };
})();

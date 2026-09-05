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
  const DEBUG = true;   // logs to the X page console; flip off once selectors are trusted

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
    caret: '[data-testid="caret"]',   // the "•••" menu button on a tweet
  };

  // Pull the post's text/author/url/image out of the article a control sits in.
  // Returns null when the element isn't inside a recognisable tweet, so callers
  // can tell "no post here" from "a post with thin detail".
  function context(fromEl) {
    const art = fromEl.closest(SEL.tweet) || fromEl.closest('article[role="article"]');
    if (!art) return null;
    const text = art.querySelector(SEL.text)?.innerText?.trim();
    const img = art.querySelector(SEL.image)?.src;
    // The status link is the tweet's permalink. Prefer the timestamp's link,
    // but fall back to any /status/ link in the article (quote tweets, layouts
    // with no <time>). Skip analytics/photo sub-paths.
    let url =
      art.querySelector(SEL.timeLink)?.closest("a")?.href ||
      [...art.querySelectorAll('a[href*="/status/"]')]
        .map((a) => a.href)
        .find((h) => /\/status\/\d+(?:$|[?#])/.test(h)) ||
      undefined;   // no permalink found — better no link than a link to the feed
    const author = art.querySelector('[data-testid="User-Name"] a[href^="/"]')
      ?.getAttribute("href")?.replace(/^\//, "@");
    return { noun: "a post", text, url, image: img, author };
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

      const ctx = context(anchor) || { noun: "a post", url: location.href };
      if (DEBUG) console.debug("[overshare] x:", action, ctx);
      const key = `${action}:${ctx.url || Math.random()}`;
      base.once(key, 2500, () => base.emit(SITE, action, ctx));
    });

    // "Not interested" is a menu item rendered in a popup detached from the
    // tweet, so by the time it's clicked the post is out of reach. Capture the
    // post when its "•••" menu is OPENED, and carry that through to the click.
    let menuCtx = null;
    base.onClick((el) => {
      // Any click inside a tweet — the "•••" button included — refreshes the
      // remembered post. Menu items live outside the article, so clicking one
      // returns null here and leaves the last real post in place.
      const ctx = context(el);
      if (ctx) { menuCtx = ctx; if (DEBUG) console.debug("[overshare] x: remembered", ctx); }
    });
    base.onClick((el) => {
      const item = el.closest('[role="menuitem"]');
      if (!item) return;
      const label = (item.innerText || "").toLowerCase();
      if (!label.includes("not interested")) return;
      const ctx = menuCtx || { noun: "a post" };
      if (DEBUG) console.debug("[overshare] x: not_interested using", ctx);
      base.once(`ni:${ctx.url || Date.now()}`, 2500, () =>
        base.emit(SITE, "not_interested", ctx));
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

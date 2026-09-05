/*
 * The site registry — one place that knows every site the extension can watch,
 * what it can watch there, and how each thing reads.
 *
 * Adding a site is adding a row here plus an adapter file. Nothing else in the
 * extension names a specific site: the options page builds its toggles from
 * this, the background filter reads its actions from this, and the content
 * script loads the adapter named here. So the whole thing stays honest — a
 * toggle can't exist for an action the code doesn't emit, and an emitted action
 * can't slip past the toggles.
 *
 * ACTIONS is the vocabulary. Each site declares which of them it supports and a
 * human label. `dwell` is universal (staying on one page/post a while) and is
 * added to every site automatically, so a site row lists only its real
 * interactions.
 */

// Every action the extension understands, with the wording the partner sees.
export const ACTIONS = {
  dwell:         { verb: "lingering on",   emoji: "👀", label: "lingering" },
  like:          { verb: "liked",          emoji: "❤️", label: "likes" },
  unlike:        { verb: "unliked",        emoji: "🤍", label: "unlikes" },
  not_interested:{ verb: "hid",            emoji: "🙈", label: "not interested" },
  repost:        { verb: "reposted",       emoji: "🔁", label: "reposts" },
  reply:         { verb: "replied to",     emoji: "💬", label: "replies" },
  upvote:        { verb: "upvoted",        emoji: "⬆️", label: "upvotes" },
  downvote:      { verb: "downvoted",      emoji: "⬇️", label: "downvotes" },
  watch:         { verb: "watching",       emoji: "▶️", label: "what i'm watching" },
  save:          { verb: "saved",          emoji: "🔖", label: "saves" },
  follow:        { verb: "followed",       emoji: "➕", label: "follows" },
  cart:          { verb: "added to cart",  emoji: "🛒", label: "adds to cart" },
};

// Sites, in the order the options page lists them. `hosts` are hostname
// suffixes (matched with endsWith on the bare hostname). `actions` are the keys
// from ACTIONS this site can emit, minus dwell (added everywhere).
export const SITES = {
  x: {
    label: "X / Twitter",
    hosts: ["x.com", "twitter.com"],
    adapter: "x",
    actions: ["like", "unlike", "not_interested", "repost", "reply", "follow"],
  },
  instagram: {
    label: "Instagram",
    hosts: ["instagram.com"],
    adapter: "instagram",
    actions: ["like", "unlike", "save", "follow"],
  },
  youtube: {
    label: "YouTube",
    hosts: ["youtube.com"],
    adapter: "youtube",
    actions: ["watch", "like", "unlike"],
  },
  reddit: {
    label: "Reddit",
    hosts: ["reddit.com"],
    adapter: "reddit",
    actions: ["upvote", "downvote", "save"],
  },
  tiktok: {
    label: "TikTok",
    hosts: ["tiktok.com"],
    adapter: "tiktok",
    actions: ["like", "unlike", "follow", "save"],
  },
  spotify: {
    label: "Spotify",
    hosts: ["open.spotify.com"],
    adapter: "spotify",
    actions: ["save"],
  },
  netflix: {
    label: "Netflix",
    hosts: ["netflix.com"],
    adapter: "netflix",
    actions: [],
  },
  amazon: {
    label: "Amazon",
    hosts: ["amazon.com", "amazon.in", "amazon.co.uk"],
    adapter: "amazon",
    actions: ["cart", "save"],
  },
  linkedin: {
    label: "LinkedIn",
    hosts: ["linkedin.com"],
    adapter: "linkedin",
    actions: ["like", "unlike"],
  },
};

/** Every action a site can emit, dwell included — what the toggles are built from. */
export function actionsFor(siteId) {
  const site = SITES[siteId];
  if (!site) return [];
  return ["dwell", ...site.actions];
}

/** Which site (if any) owns this hostname. */
export function siteForHost(hostname) {
  const h = String(hostname || "").toLowerCase().replace(/^www\./, "");
  for (const [id, site] of Object.entries(SITES)) {
    if (site.hosts.some((suffix) => h === suffix || h.endsWith("." + suffix))) {
      return id;
    }
  }
  return null;
}

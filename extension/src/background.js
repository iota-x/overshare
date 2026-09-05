/*
 * The service worker: the single door events leave by.
 *
 * Content scripts only *detect* — they send a raw event here and this decides,
 * against the toggles, whether it may go, then posts it to the Discord webhook
 * as a card that matches the desktop app's look. Enforcing the toggles here (not
 * in the content scripts) means one gate for every site and every future one:
 * a detector cannot leak past a switch that's off, because it never does the
 * sending itself.
 */

import { load, allowed } from "./config.js";
import { ACTIONS, SITES } from "./registry.js";

const COLOR = 0xb794f6;   // the app's soft violet

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg?.type !== "overshare-event") return;
  handle(msg.event, sender)
    .then(() => sendResponse({ ok: true }))
    .catch((e) => sendResponse({ ok: false, error: String(e) }));
  return true;   // async response
});

async function handle(event, sender) {
  const cfg = await load();
  const incognito = Boolean(sender?.tab?.incognito);
  if (!allowed(cfg, event.site, event.action, { incognito })) return;
  await post(cfg.webhook, card(event));
}

/** Build the Discord embed for one event. */
function card(event) {
  const site = SITES[event.site];
  const act = ACTIONS[event.action] || { verb: event.action, emoji: "•" };
  const siteName = site?.label || event.site;

  // "❤️ liked a post on X"  — the headline. The detail (post text) is the body.
  const headline = `${act.emoji} ${act.verb} ${event.noun || "something"} on ${siteName}`;

  const embed = {
    author: { name: headline },
    color: COLOR,
    footer: { text: "in detail · browser" },
    timestamp: new Date().toISOString(),
  };
  if (event.text) embed.description = String(event.text).slice(0, 400);
  if (event.url) embed.url = event.url;
  if (event.title) embed.title = String(event.title).slice(0, 250);
  if (event.image && /^https?:\/\//.test(event.image)) {
    embed.thumbnail = { url: event.image };
  }
  const fields = [];
  if (event.author) fields.push({ name: "by", value: String(event.author).slice(0, 100), inline: true });
  if (event.minutes >= 1) fields.push({ name: "⏱ for", value: `${event.minutes} min`, inline: true });
  if (fields.length) embed.fields = fields;
  return embed;
}

async function post(webhook, embed) {
  try {
    const res = await fetch(webhook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ embeds: [embed] }),
    });
    if (!res.ok && res.status === 429) {
      // Rate limited — wait what Discord asks, then try once more.
      const retry = Number(res.headers.get("retry-after")) || 1;
      await new Promise((r) => setTimeout(r, retry * 1000));
      await fetch(webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ embeds: [embed] }),
      });
    }
  } catch (e) {
    // A failed send is dropped on purpose. This is ambient sharing, not a
    // message queue; retrying a stale "liked a post" minutes later would be
    // worse than losing it.
    console.warn("[overshare] webhook post failed:", e);
  }
}

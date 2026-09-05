/*
 * The options page: master switch, webhook, and a block of toggles per site —
 * one for the whole site, then one per action under it. All of it is built from
 * the registry, so a site or action added there appears here with no edit.
 *
 * Writes straight to chrome.storage.sync on every change (no Save button to
 * forget), and the background reads the same store when it decides what may go.
 */

import { SITES, ACTIONS, actionsFor } from "./registry.js";
import { load, save } from "./config.js";

const $ = (id) => document.getElementById(id);
let cfg;

function flashSaved() {
  const el = $("saved");
  el.classList.add("show");
  clearTimeout(flashSaved._t);
  flashSaved._t = setTimeout(() => el.classList.remove("show"), 900);
}

async function persist() {
  await save({
    enabled: cfg.enabled,
    webhook: cfg.webhook,
    sites: cfg.sites,
    captureIncognito: cfg.captureIncognito,
  });
  flashSaved();
}

function buildSites() {
  const root = $("sites");
  root.innerHTML = "";
  for (const [id, site] of Object.entries(SITES)) {
    const card = document.createElement("section");
    card.className = "card site";

    const head = document.createElement("label");
    head.className = "row site-head";
    head.innerHTML = `<span><b>${site.label}</b></span>`;
    const siteToggle = document.createElement("input");
    siteToggle.type = "checkbox";
    siteToggle.checked = !!cfg.sites[id].on;
    siteToggle.addEventListener("change", () => {
      cfg.sites[id].on = siteToggle.checked;
      card.classList.toggle("off", !siteToggle.checked);
      persist();
    });
    head.appendChild(siteToggle);
    card.appendChild(head);

    const actions = document.createElement("div");
    actions.className = "actions";
    for (const a of actionsFor(id)) {
      const meta = ACTIONS[a] || { verb: a, emoji: "•" };
      const line = document.createElement("label");
      line.className = "row action";
      line.innerHTML = `<span>${meta.emoji} ${labelFor(a, meta)}</span>`;
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = !!cfg.sites[id].actions[a];
      box.addEventListener("change", () => {
        cfg.sites[id].actions[a] = box.checked;
        persist();
      });
      line.appendChild(box);
      actions.appendChild(line);
    }
    card.appendChild(actions);
    card.classList.toggle("off", !cfg.sites[id].on);
    root.appendChild(card);
  }
}

function labelFor(action, meta) {
  // Clean wording lives on the action itself in the registry.
  return meta.label || action;
}

async function main() {
  cfg = await load();

  $("enabled").checked = cfg.enabled;
  $("enabled").addEventListener("change", (e) => {
    cfg.enabled = e.target.checked;
    persist();
  });

  $("webhook").value = cfg.webhook;
  $("webhook").addEventListener("change", (e) => {
    cfg.webhook = e.target.value.trim();
    persist();
  });

  $("captureIncognito").checked = cfg.captureIncognito;
  $("captureIncognito").addEventListener("change", (e) => {
    cfg.captureIncognito = e.target.checked;
    persist();
  });

  $("test").addEventListener("click", async () => {
    const status = $("teststatus");
    const url = $("webhook").value.trim();
    if (!url) { status.textContent = "paste the webhook URL first"; return; }
    status.textContent = "sending…";
    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          embeds: [{
            author: { name: "👋 Overshare — browser is connected" },
            description: "If you can see this, the extension can reach your channel.",
            color: 0xb794f6,
            footer: { text: "in detail · browser" },
            timestamp: new Date().toISOString(),
          }],
        }),
      });
      status.textContent = res.ok ? "sent ✓ check the channel" : `failed (${res.status})`;
    } catch (e) {
      status.textContent = "failed — is the URL right?";
    }
  });

  buildSites();
}

main();

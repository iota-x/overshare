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
    const bank = document.createElement("div");
    bank.className = "bank";

    const head = document.createElement("label");
    head.className = "site-head";
    head.innerHTML = `<span class="site-name">${site.label}</span>`;
    const siteToggle = document.createElement("input");
    siteToggle.type = "checkbox";
    siteToggle.checked = !!cfg.sites[id].on;
    siteToggle.addEventListener("change", () => {
      cfg.sites[id].on = siteToggle.checked;
      bank.classList.toggle("off", !siteToggle.checked);
      persist();
    });
    head.appendChild(siteToggle);
    bank.appendChild(head);

    const switches = document.createElement("div");
    switches.className = "switches";
    for (const a of actionsFor(id)) {
      const meta = ACTIONS[a] || { verb: a, emoji: "•", label: a };
      const row = document.createElement("label");
      row.className = "switch-row";
      row.innerHTML =
        `<span class="name"><span class="em">${meta.emoji}</span>${meta.label || a}</span>`;
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = !!cfg.sites[id].actions[a];
      box.addEventListener("change", () => {
        cfg.sites[id].actions[a] = box.checked;
        persist();
      });
      row.appendChild(box);
      switches.appendChild(row);
    }
    bank.appendChild(switches);
    bank.classList.toggle("off", !cfg.sites[id].on);
    root.appendChild(bank);
  }
}

async function main() {
  cfg = await load();

  const reflectAir = (on) => {
    document.body.classList.toggle("live", on);
    $("stateword").textContent = on ? "on air" : "off air";
    $("statesub").textContent = on
      ? "sharing what you switch on below"
      : "nothing is going out";
  };
  $("enabled").checked = cfg.enabled;
  reflectAir(cfg.enabled);
  $("enabled").addEventListener("change", (e) => {
    cfg.enabled = e.target.checked;
    reflectAir(cfg.enabled);
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

/*
 * Stored settings and the one rule that decides whether an event may be sent.
 *
 * Everything here is off until turned on. A fresh install captures nothing: no
 * webhook, master switch off, every site off. That is the only safe default for
 * something that watches what you do.
 *
 * Layout in chrome.storage.sync:
 *   webhook            string   the Discord webhook URL ("" = not set)
 *   enabled            bool     master switch
 *   sites              { [siteId]: { on: bool, actions: { [action]: bool } } }
 *   captureIncognito   bool     whether to fire in incognito windows (default off)
 *   quietDms           bool     never fire on DM/message screens (default on)
 */

import { SITES, actionsFor } from "./registry.js";

export function defaults() {
  const sites = {};
  for (const id of Object.keys(SITES)) {
    const actions = {};
    for (const a of actionsFor(id)) actions[a] = false;   // every action starts off
    sites[id] = { on: false, actions };
  }
  return {
    webhook: "",
    enabled: false,
    sites,
    captureIncognito: false,
    quietDms: true,
  };
}

/** Read the whole config, filling any gaps (new sites/actions) with off. */
export async function load() {
  const stored = await chrome.storage.sync.get(null);
  const base = defaults();
  const cfg = { ...base, ...stored };
  // Merge site-by-site so a site or action added in an update appears (off).
  cfg.sites = { ...base.sites, ...(stored.sites || {}) };
  for (const id of Object.keys(base.sites)) {
    cfg.sites[id] = {
      on: cfg.sites[id]?.on ?? false,
      actions: { ...base.sites[id].actions, ...(cfg.sites[id]?.actions || {}) },
    };
  }
  return cfg;
}

export async function save(patch) {
  await chrome.storage.sync.set(patch);
}

/**
 * The gate. Every event passes through here before anything leaves the browser,
 * so the toggles are honored in exactly one place no matter which adapter fired
 * or how a future one is written.
 *
 * `incognito` is whether the tab that fired is an incognito tab.
 */
export function allowed(cfg, siteId, action, { incognito = false } = {}) {
  if (!cfg.enabled) return false;
  if (!cfg.webhook) return false;
  if (incognito && !cfg.captureIncognito) return false;
  const site = cfg.sites[siteId];
  if (!site || !site.on) return false;
  return site.actions[action] === true;
}

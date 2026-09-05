/*
 * Amazon adapter.
 *
 * The interesting signals: adding to cart, saving for later / to a list, and
 * lingering on a product (that "should I?" hover). Product pages are /dp/<asin>
 * or /gp/product/<asin>. Buttons carry stable ids (add-to-cart-button).
 *
 * NOT YET tuned against a live session, and Amazon's markup varies by locale.
 */

(function () {
  const NS = (window.__overshare = window.__overshare || {});
  const SITE = "amazon";

  function asin() {
    const m = location.pathname.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/);
    return m ? m[1] : null;
  }

  function context() {
    const title = document.getElementById("productTitle")?.innerText?.trim()
      || document.querySelector('meta[name="title"]')?.content
      || document.title.replace(/ [:|-] Amazon.*$/i, "");
    const img = document.getElementById("landingImage")?.src
      || document.querySelector('meta[property="og:image"]')?.content;
    return { noun: "a product", title, image: img, url: location.href };
  }

  function init(base) {
    base.onClick((el) => {
      if (el.closest('#add-to-cart-button, [name="submit.add-to-cart"], #add-to-cart-button-ubb')) {
        base.once(`cart:${asin() || location.href}`, 3000, () => base.emit(SITE, "cart", context()));
        return;
      }
      if (el.closest('#add-to-wishlist-button, #wishlistButtonStack, [name="submit.add-to-registry.wishlist"]')) {
        base.once(`save:${asin() || location.href}`, 3000, () => base.emit(SITE, "save", context()));
      }
    });

    base.watchDwell(
      () => {
        const id = asin();
        return id ? { site: SITE, key: id } : null;
      },
      { seconds: 75, noun: "a product", detail: () => context() },
    );
  }

  NS.adapter = { init };
})();

/* Scroll deck for the home work list.
   Wide screens with motion: cards rotate in one sticky stage.
   Small screens and reduced motion keep the static list.
*/
(function () {
  "use strict";

  var deck = document.querySelector("[data-deck]");
  if (!deck) return;

  var pin = deck.querySelector(".deck-pin");
  var cards = Array.prototype.slice.call(deck.querySelectorAll(".deck-card"));
  var nowEl = deck.querySelector("[data-deck-now]");
  var barEl = deck.querySelector("[data-deck-bar]");
  var reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  var wideQuery = window.matchMedia("(min-width: 800px)");
  var root = document.documentElement;
  var on = false;
  var raf = 0;
  var metrics = { start: 0, range: 1 };

  function clamp(v, a, b) {
    return Math.max(a, Math.min(b, v));
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function wantsDeck() {
    return cards.length > 1 && !reduceQuery.matches && wideQuery.matches;
  }

  function clearCard(card) {
    card.style.transform = "";
    card.style.opacity = "";
    card.style.zIndex = "";
    var link = card.querySelector(".card");
    if (link) link.style.pointerEvents = "";
  }

  function measure() {
    var sticky = parseFloat(window.getComputedStyle(pin).top) || 0;
    metrics.start = deck.getBoundingClientRect().top + window.scrollY - sticky;
    metrics.range = Math.max(1, deck.offsetHeight - pin.offsetHeight);
  }

  function progress() {
    return clamp((window.scrollY - metrics.start) / metrics.range, 0, 1);
  }

  function place(rel) {
    var past = rel < 0 ? -rel : 0;
    var next = rel > 0 ? rel : 0;
    var rotateX = 16 + next * 7 - past * 62;
    var y = next * 26 - past * 120;
    var z = -110 * next + past * 70;
    var scale = 1 - next * 0.055 - past * 0.04;
    var opacity = 1;
    if (next > 2.15) opacity = clamp(1 - (next - 2.15) / 0.75, 0, 1);
    if (past > 0.42) opacity = clamp(1 - (past - 0.42) / 0.4, 0, 1);
    var zIndex = past > 0 && past < 0.9 ? 48 : 24 - Math.round(next * 4);
    var hit = rel >= -0.32 && rel < 0.62 && opacity > 0.45;
    return {
      rotateX: rotateX,
      y: y,
      z: z,
      scale: scale,
      opacity: opacity,
      zIndex: zIndex,
      hit: hit
    };
  }

  function render() {
    raf = 0;
    if (!on) return;
    var p = progress();
    var active = p * (cards.length - 1);
    var shown = Math.round(active) + 1;
    if (nowEl) nowEl.textContent = pad(shown);
    if (barEl) barEl.style.transform = "scaleX(" + p.toFixed(4) + ")";

    var i;
    for (i = 0; i < cards.length; i += 1) {
      var spot = place(i - active);
      var card = cards[i];
      var link = card.querySelector(".card");
      card.style.opacity = spot.opacity.toFixed(3);
      card.style.zIndex = String(spot.zIndex);
      card.style.transform =
        "translate3d(0," + spot.y.toFixed(1) + "px," + spot.z.toFixed(1) + "px) " +
        "rotateX(" + spot.rotateX.toFixed(2) + "deg) " +
        "scale(" + spot.scale.toFixed(3) + ")";
      if (link) link.style.pointerEvents = spot.hit ? "auto" : "none";
    }
  }

  function requestRender() {
    if (!on || raf) return;
    raf = window.requestAnimationFrame(render);
  }

  function scrollToCard(index) {
    if (!on) return;
    measure();
    var t = cards.length === 1 ? 0 : index / (cards.length - 1);
    window.scrollTo({ top: metrics.start + t * metrics.range, behavior: "auto" });
    render();
  }

  function enable() {
    if (on) return;
    on = true;
    deck.style.setProperty("--n", String(cards.length));
    root.classList.add("deck-on");
    measure();
    render();
  }

  function disable() {
    if (!on && !root.classList.contains("deck-on")) return;
    on = false;
    if (raf) window.cancelAnimationFrame(raf);
    raf = 0;
    root.classList.remove("deck-on");
    cards.forEach(clearCard);
    if (barEl) barEl.style.transform = "scaleX(0)";
  }

  function sync() {
    if (wantsDeck()) enable();
    else disable();
  }

  cards.forEach(function (card, index) {
    var link = card.querySelector(".card");
    if (!link) return;
    link.addEventListener("focus", function () {
      if (!on) return;
      scrollToCard(index);
    });
  });

  deck.addEventListener("keydown", function (e) {
    if (!on) return;
    var dir = 0;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") dir = 1;
    if (e.key === "ArrowUp" || e.key === "ArrowLeft") dir = -1;
    if (!dir) return;
    var links = cards.map(function (card) { return card.querySelector(".card"); });
    var idx = links.indexOf(document.activeElement);
    if (idx < 0) return;
    var next = links[idx + dir];
    if (!next) return;
    e.preventDefault();
    next.focus();
  });

  window.addEventListener("scroll", requestRender, { passive: true });
  window.addEventListener("resize", function () {
    sync();
    if (on) {
      measure();
      requestRender();
    }
  });

  if (window.ResizeObserver) {
    var observer = new ResizeObserver(function () {
      if (!on) return;
      measure();
      requestRender();
    });
    observer.observe(deck);
  }

  function onMedia() {
    sync();
  }

  if (reduceQuery.addEventListener) {
    reduceQuery.addEventListener("change", onMedia);
    wideQuery.addEventListener("change", onMedia);
  } else if (reduceQuery.addListener) {
    reduceQuery.addListener(onMedia);
    wideQuery.addListener(onMedia);
  }

  sync();
})();

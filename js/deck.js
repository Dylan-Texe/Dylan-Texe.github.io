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
  var tilt = { i: -1, x: 0, y: 0 };

  function clamp(v, a, b) {
    return Math.max(a, Math.min(b, v));
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function smooth(t) {
    t = clamp(t, 0, 1);
    return t * t * (3 - 2 * t);
  }

  function wantsDeck() {
    return cards.length > 1 && !reduceQuery.matches && wideQuery.matches;
  }

  function clearCard(card) {
    card.style.transform = "";
    card.style.opacity = "";
    card.style.zIndex = "";
    var link = card.querySelector(".card");
    if (!link) return;
    link.style.pointerEvents = "";
    link.style.opacity = "";
    link.style.transform = "";
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
    var pastRaw = rel < 0 ? -rel : 0;
    var nextRaw = rel > 0 ? rel : 0;
    var past = Math.min(pastRaw, 1.05);
    var next = Math.min(nextRaw, 2.6);
    var arrive = smooth(Math.min(nextRaw, 1));
    var rotateX = 14 + arrive * 6 - past * 42;
    var rotateY = arrive * -2.5 + past * 4;
    var y = next * 22 - past * 16;
    var z = -90 * next + past * 18;
    var scale = 1 - next * 0.07 - past * 0.05;
    var opacity = 1;
    if (nextRaw > 0) opacity = clamp(1 - Math.pow(nextRaw, 0.85) * 1.08, 0, 1);
    if (pastRaw > 0.42) opacity = Math.min(opacity, clamp(1 - (pastRaw - 0.42) / 0.45, 0, 1));
    var hit = rel >= -0.28 && rel < 0.55 && opacity > 0.5;
    return {
      rotateX: rotateX,
      rotateY: rotateY,
      y: y,
      z: z,
      scale: scale,
      opacity: opacity,
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
      card.style.transform =
        "translate3d(0," + spot.y.toFixed(1) + "px," + spot.z.toFixed(1) + "px) " +
        "rotateX(" + spot.rotateX.toFixed(2) + "deg) " +
        "rotateY(" + spot.rotateY.toFixed(2) + "deg) " +
        "scale(" + spot.scale.toFixed(3) + ")";
      if (link) {
        link.style.opacity = spot.opacity.toFixed(3);
        link.style.pointerEvents = spot.hit ? "auto" : "none";
        if (tilt.i === i && spot.hit) {
          link.style.transform =
            "rotateX(" + (-tilt.y * 24).toFixed(2) + "deg) " +
            "rotateY(" + (tilt.x * 30).toFixed(2) + "deg)";
        } else {
          link.style.transform = "";
        }
      }
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
    link.addEventListener("pointermove", function (e) {
      if (reduceQuery.matches) return;
      if (e.pointerType && e.pointerType !== "mouse") return;
      var rect = link.getBoundingClientRect();
      var px = (e.clientX - rect.left) / Math.max(1, rect.width) - 0.5;
      var py = (e.clientY - rect.top) / Math.max(1, rect.height) - 0.5;
      link.style.setProperty("--gx", ((px + 0.5) * 100).toFixed(1) + "%");
      link.style.setProperty("--gy", ((py + 0.5) * 100).toFixed(1) + "%");
      if (on) {
        tilt.i = index;
        tilt.x = px;
        tilt.y = py;
        requestRender();
        return;
      }
      link.style.transform =
        "rotateX(" + (-py * 22).toFixed(2) + "deg) rotateY(" + (px * 28).toFixed(2) + "deg)";
    });
    link.addEventListener("pointerleave", function () {
      link.style.removeProperty("--gx");
      link.style.removeProperty("--gy");
      if (tilt.i === index) {
        tilt.i = -1;
        tilt.x = 0;
        tilt.y = 0;
      }
      if (on) requestRender();
      else link.style.transform = "";
    });
  });

  var hero = document.querySelector(".hero");
  if (hero) {
    hero.addEventListener("pointermove", function (e) {
      if (reduceQuery.matches) return;
      if (e.pointerType && e.pointerType !== "mouse") return;
      var rect = hero.getBoundingClientRect();
      hero.style.setProperty("--hx", ((e.clientX - rect.left) / Math.max(1, rect.width) * 100).toFixed(1) + "%");
      hero.style.setProperty("--hy", ((e.clientY - rect.top) / Math.max(1, rect.height) * 100).toFixed(1) + "%");
    });
  }

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

/* Horizontal work carousel.
   Drag, wheel, swipe, arrows, and keyboard.
   Phones snap to the start of each card. Wide screens center the active card.
   Reduced motion keeps the snap track and skips tilt, shine, and the idle nudge.
*/
(function () {
  "use strict";

  var root = document.querySelector("[data-carousel]");
  if (!root) return;

  var track = root.querySelector("[data-carousel-track]");
  var slides = track ? Array.prototype.slice.call(track.children) : [];
  if (!track || slides.length === 0) return;

  var prevBtn = root.querySelector("[data-carousel-prev]");
  var nextBtn = root.querySelector("[data-carousel-next]");
  var fractionEl = root.querySelector("[data-carousel-fraction]");
  var barEl = root.querySelector("[data-carousel-bar]");
  var liveEl = root.querySelector("[data-carousel-live]");
  var dotsEl = root.querySelector("[data-carousel-dots]");
  var wideQuery = window.matchMedia("(min-width: 960px)");
  var reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  var fineQuery = window.matchMedia("(hover: hover) and (pointer: fine)");
  var index = 0;
  var lock = false;
  var interacted = false;
  var nudged = false;
  var announced = false;
  var swallowClick = false;
  var drag = { on: false, id: 0, x: 0, left: 0, moved: false };
  var dots = [];
  var lockTimer = 0;

  function holdLock(ms) {
    lock = true;
    window.clearTimeout(lockTimer);
    lockTimer = window.setTimeout(function () {
      lock = false;
      if (!drag.on) syncFromScroll();
    }, ms);
  }

  function reduced() {
    return reduceQuery.matches;
  }

  function wide() {
    return wideQuery.matches;
  }

  function clampIndex(i) {
    if (i < 0) return 0;
    if (i > slides.length - 1) return slides.length - 1;
    return i;
  }

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  function nameOf(i) {
    var heading = slides[i].querySelector("h3");
    return heading ? heading.textContent.replace(/\s+/g, " ").trim() : "Project " + (i + 1);
  }

  function behavior(kind) {
    if (kind) return kind;
    return reduced() ? "auto" : "smooth";
  }

  function targetLeft(i) {
    var slide = slides[i];
    var left = slide.offsetLeft;
    if (!wide()) return left - slides[0].offsetLeft;
    return left - (track.clientWidth - slide.offsetWidth) / 2;
  }

  function clampScroll(left) {
    var max = Math.max(0, track.scrollWidth - track.clientWidth);
    if (left < 0) return 0;
    if (left > max) return max;
    return left;
  }

  function nearestIndex() {
    var trackRect = track.getBoundingClientRect();
    var best = 0;
    var bestDist = Infinity;
    var i;
    if (wide()) {
      var mid = trackRect.left + trackRect.width / 2;
      for (i = 0; i < slides.length; i += 1) {
        var box = slides[i].getBoundingClientRect();
        var delta = Math.abs(box.left + box.width / 2 - mid);
        if (delta < bestDist) {
          bestDist = delta;
          best = i;
        }
      }
      return best;
    }
    var pad = parseFloat(window.getComputedStyle(track).paddingLeft) || 0;
    var edge = trackRect.left + pad;
    for (i = 0; i < slides.length; i += 1) {
      var dist = Math.abs(slides[i].getBoundingClientRect().left - edge);
      if (dist < bestDist) {
        bestDist = dist;
        best = i;
      }
    }
    return best;
  }

  function paint() {
    var i;
    for (i = 0; i < slides.length; i += 1) {
      slides[i].classList.toggle("is-active", i === index);
      slides[i].classList.toggle("is-before", i < index);
      slides[i].classList.toggle("is-after", i > index);
      if (dots[i]) {
        if (i === index) dots[i].setAttribute("aria-current", "true");
        else dots[i].removeAttribute("aria-current");
      }
    }
    if (fractionEl) fractionEl.textContent = pad(index + 1) + " / " + pad(slides.length);
    if (barEl) {
      var span = slides.length === 1 ? 1 : index / (slides.length - 1);
      barEl.style.width = (8 + span * 92).toFixed(2) + "%";
    }
    if (prevBtn) prevBtn.disabled = index === 0;
    if (nextBtn) nextBtn.disabled = index === slides.length - 1;
    if (liveEl && announced) {
      liveEl.textContent = nameOf(index) + ", " + (index + 1) + " of " + slides.length;
    }
  }

  function go(i, how) {
    index = clampIndex(i);
    announced = true;
    interacted = true;
    paint();
    holdLock(reduced() || how === "auto" ? 70 : 640);
    track.scrollTo({ left: clampScroll(targetLeft(index)), behavior: behavior(how) });
  }

  function syncFromScroll() {
    if (lock || drag.on) return;
    var next = nearestIndex();
    if (next === index) return;
    index = next;
    paint();
  }

  function focusCard(i) {
    var link = slides[i].querySelector(".card");
    if (!link) return;
    try {
      link.focus({ preventScroll: true });
    } catch (err) {
      link.focus();
    }
  }

  if (dotsEl) {
    var d;
    for (d = 0; d < slides.length; d += 1) {
      var dot = document.createElement("button");
      dot.type = "button";
      dot.className = "dot";
      dot.setAttribute("aria-label", "Show " + nameOf(d));
      dot.addEventListener("click", (function (n) {
        return function () { go(n); };
      })(d));
      dotsEl.appendChild(dot);
      dots.push(dot);
    }
  }

  if (prevBtn) prevBtn.addEventListener("click", function () { go(index - 1); });
  if (nextBtn) nextBtn.addEventListener("click", function () { go(index + 1); });

  root.addEventListener("keydown", function (e) {
    if (e.altKey || e.metaKey || e.ctrlKey) return;
    var dir = 0;
    if (e.key === "ArrowRight") dir = 1;
    if (e.key === "ArrowLeft") dir = -1;
    if (e.key === "Home") dir = -999;
    if (e.key === "End") dir = 999;
    if (!dir) return;
    e.preventDefault();
    var fromCard = e.target.closest && e.target.closest(".card");
    var next = dir === -999 ? 0 : dir === 999 ? slides.length - 1 : index + dir;
    go(next);
    if (fromCard) focusCard(index);
  });

  track.addEventListener("pointerdown", function (e) {
    if (e.pointerType !== "mouse" || e.button !== 0) return;
    interacted = true;
    drag.on = true;
    drag.moved = false;
    drag.id = e.pointerId;
    drag.x = e.clientX;
    drag.left = track.scrollLeft;
    lock = false;
    track.classList.add("is-dragging");
    try { track.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
  });

  track.addEventListener("pointermove", function (e) {
    if (drag.on && e.pointerId === drag.id) {
      var dx = e.clientX - drag.x;
      if (Math.abs(dx) > 8) drag.moved = true;
      track.scrollLeft = drag.left - dx;
      return;
    }
    if (!fineQuery.matches || reduced() || !wide()) return;
    var card = slides[index].querySelector(".card");
    if (!card) return;
    var rect = card.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) return;
    var px = (e.clientX - rect.left) / rect.width;
    var py = (e.clientY - rect.top) / rect.height;
    if (px < -0.2 || px > 1.2 || py < -0.2 || py > 1.2) return;
    var tilt = Math.max(-6, Math.min(6, (px - 0.5) * -10));
    var lift = Math.max(-4, Math.min(4, (0.5 - py) * 7));
    card.style.setProperty("--tilt", tilt.toFixed(2) + "deg");
    card.style.setProperty("--lift", lift.toFixed(2) + "deg");
    card.style.setProperty("--gx", (Math.max(0, Math.min(1, px)) * 100).toFixed(1) + "%");
    card.style.setProperty("--gy", (Math.max(0, Math.min(1, py)) * 100).toFixed(1) + "%");
  });

  function endDrag(e) {
    if (!drag.on || (e && e.pointerId !== drag.id)) return;
    var moved = drag.moved;
    drag.on = false;
    track.classList.remove("is-dragging");
    if (!moved) return;
    swallowClick = true;
    index = nearestIndex();
    announced = true;
    paint();
    holdLock(reduced() ? 70 : 520);
    track.scrollTo({ left: clampScroll(targetLeft(index)), behavior: behavior() });
  }

  track.addEventListener("pointerup", endDrag);
  track.addEventListener("pointercancel", endDrag);
  track.addEventListener("dragstart", function (e) { e.preventDefault(); });
  track.addEventListener("click", function (e) {
    if (!swallowClick) return;
    swallowClick = false;
    e.preventDefault();
    e.stopPropagation();
  }, true);

  track.addEventListener("scroll", function () {
    if (lock || drag.on) return;
    window.requestAnimationFrame(syncFromScroll);
  }, { passive: true });

  track.addEventListener("scrollend", function () {
    window.clearTimeout(lockTimer);
    lock = false;
    if (!drag.on) syncFromScroll();
  });

  track.addEventListener("wheel", function () { interacted = true; }, { passive: true });
  track.addEventListener("touchstart", function () { interacted = true; }, { passive: true });

  function realign() {
    if (drag.on) return;
    holdLock(90);
    track.scrollTo({ left: clampScroll(targetLeft(index)), behavior: "auto" });
  }

  window.addEventListener("resize", realign);
  if (window.ResizeObserver) {
    var observer = new ResizeObserver(realign);
    observer.observe(track);
  }

  function onMedia() {
    slides.forEach(function (slide) {
      var card = slide.querySelector(".card");
      if (!card) return;
      card.style.removeProperty("--tilt");
      card.style.removeProperty("--lift");
    });
    realign();
    paint();
  }

  if (wideQuery.addEventListener) {
    wideQuery.addEventListener("change", onMedia);
    reduceQuery.addEventListener("change", onMedia);
  } else if (wideQuery.addListener) {
    wideQuery.addListener(onMedia);
    reduceQuery.addListener(onMedia);
  }

  function scheduleNudge() {
    if (nudged || reduced()) return;
    window.setTimeout(function () {
      if (nudged || interacted || reduced() || index !== 0 || document.hidden) return;
      nudged = true;
      var max = track.scrollWidth - track.clientWidth;
      if (max < 24) return;
      var delta = Math.min(wide() ? 68 : 36, max);
      holdLock(1700);
      track.scrollTo({ left: delta, behavior: "smooth" });
      window.setTimeout(function () {
        if (interacted) {
          lock = false;
          syncFromScroll();
          return;
        }
        track.scrollTo({ left: clampScroll(targetLeft(0)), behavior: "smooth" });
      }, 820);
    }, 900);
  }

  if ("IntersectionObserver" in window) {
    var seen = false;
    var watch = new IntersectionObserver(function (entries) {
      if (seen || !entries[0].isIntersecting) return;
      seen = true;
      scheduleNudge();
      watch.disconnect();
    }, { threshold: 0.45 });
    watch.observe(track);
  } else {
    scheduleNudge();
  }

  paint();
  realign();
})();

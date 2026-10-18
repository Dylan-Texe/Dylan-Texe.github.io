/* Pause looping CSS animations that are off screen.
   Any element with data-motion gets is-offscreen while it is out of view,
   and the stylesheet pauses every animation inside it.
   Slides hidden sideways in the carousel count as off screen too.
*/
(function () {
  "use strict";

  if (!("IntersectionObserver" in window)) return;
  var nodes = document.querySelectorAll("[data-motion]");
  if (!nodes.length) return;

  var watch = new IntersectionObserver(function (entries) {
    for (var i = 0; i < entries.length; i += 1) {
      entries[i].target.classList.toggle("is-offscreen", !entries[i].isIntersecting);
    }
  }, { rootMargin: "80px" });

  for (var i = 0; i < nodes.length; i += 1) watch.observe(nodes[i]);
})();

/* TARGET_PLAY_URL
   Live builds. Change a constant here to retarget Play.
   GitHub is source only and is not these URLs.
*/
var UFO_PLAY_URL = "https://ufo-80s.vercel.app";
var PENTASPACE_URL = "https://pentaspace.vercel.app";

(function () {
  var map = {
    UFO_PLAY_URL: UFO_PLAY_URL,
    PENTASPACE_URL: PENTASPACE_URL,
  };
  var nodes = document.querySelectorAll("[data-play-url]");
  for (var i = 0; i < nodes.length; i += 1) {
    var key = nodes[i].getAttribute("data-play-url");
    if (map[key]) nodes[i].setAttribute("href", map[key]);
  }
})();

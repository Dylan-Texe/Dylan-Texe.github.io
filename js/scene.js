/* Living vapor scene.
   Planets, stars, matrix rain, and a perspective floor.
   Static SVG stays in place when motion is reduced or this script fails.
*/
(function () {
  "use strict";

  var reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  var STAR_SRC = "754,514,1.0,0.55 1317,403,0.7,0.55 1462,290,0.7,0.55 234,546,1.15,0.75 1401,207,0.8,0.9 1463,158,1.0,0.75 1051,265,1.0,0.9 843,379,1.15,0.55 1042,343,1.5,0.55 1319,530,1.0,0.4 847,105,1.15,0.55 281,58,1.15,0.75 430,535,1.5,0.9 601,24,1.5,0.55 642,435,0.7,0.9 443,530,1.15,0.75 401,133,1.5,0.55 1271,34,1.0,0.55 409,51,1.15,0.9 1406,178,1.15,0.55 265,49,1.15,0.75 1090,77,0.7,0.4 1281,322,0.8,0.4 748,449,0.7,0.55 1506,161,0.8,0.9 1363,327,0.8,0.4 758,53,0.7,0.55 1565,268,0.8,0.9 220,105,1.0,0.75 261,288,1.0,0.4 598,332,1.15,0.55 1446,432,0.8,0.9 1306,464,1.15,0.4 274,323,1.5,0.75 1553,116,0.8,0.9 37,363,0.7,0.4 1199,74,0.7,0.4 1050,277,0.8,0.4 794,354,1.0,0.75 763,457,1.5,0.75 1320,220,1.5,0.55 223,360,0.8,0.55 1049,86,0.8,0.75 740,106,0.7,0.4 700,247,0.8,0.55 1340,10,0.8,0.4 252,172,0.7,0.4 1408,47,1.15,0.75 990,26,0.7,0.75 22,59,0.7,0.4 756,185,1.0,0.55 470,305,1.0,0.9 1461,274,0.7,0.75 511,223,1.0,0.75 1450,77,1.0,0.55 885,51,0.7,0.75 1449,68,0.8,0.55 1413,113,1.15,0.55 395,460,1.5,0.4 944,430,0.7,0.4 1377,163,1.5,0.75 985,59,1.15,0.9 286,548,1.15,0.75 357,122,0.7,0.4 1042,13,0.7,0.4 1386,312,0.7,0.9 1415,547,0.7,0.55 445,104,1.5,0.9 28,74,0.7,0.55 1506,518,0.7,0.75 32,410,0.7,0.55 159,74,0.8,0.9 1308,307,1.0,0.55 407,407,1.5,0.4 1288,288,1.15,0.9 31,202,1.5,0.55 1088,398,0.7,0.55 13,357,0.7,0.4 1486,234,1.15,0.75 1292,325,1.0,0.4 952,380,0.8,0.55 1321,30,1.5,0.55 593,72,1.5,0.75 884,332,0.8,0.9 361,144,1.0,0.4 541,118,0.8,0.55 356,308,0.7,0.9 444,344,1.15,0.75 1258,85,1.5,0.4 1382,31,1.15,0.55 69,241,1.0,0.75 1385,310,0.7,0.9 188,325,1.5,0.9 1472,368,1.5,0.55 277,122,0.7,0.9 987,280,1.5,0.55 619,324,1.5,0.55 1402,507,0.8,0.55 1343,215,1.0,0.4 887,302,0.7,0.55 228,245,1.0,0.55 491,253,1.0,0.9 1307,286,0.8,0.4 213,448,1.0,0.75";
  var CROSS = [
    { x: 240, y: 113, s: 7 },
    { x: 1180, y: 84, s: 6 },
    { x: 995, y: 198, s: 5 },
    { x: 434, y: 246, s: 4 }
  ];
  var RIDGE_A = [[0, 86], [100, 40], [170, 74], [250, 28], [340, 78], [430, 36], [520, 18], [610, 70], [710, 34], [800, 14], [900, 66], [990, 30], [1090, 72], [1180, 26], [1280, 64], [1380, 22], [1470, 60], [1600, 78]];
  var RIDGE_B = [[0, 118], [140, 82], [250, 110], [360, 76], [480, 116], [600, 84], [730, 120], [860, 86], [990, 114], [1120, 78], [1260, 112], [1400, 80], [1600, 116]];
  var GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEFZ$+*<>/=#";

  var STARS = STAR_SRC.split(" ").map(function (row) {
    var p = row.split(",");
    return { x: +p[0], y: +p[1], r: +p[2], a: +p[3] };
  });

  var root = document.documentElement;
  var running = false;
  var booted = false;
  var raf = 0;
  var last = 0;
  var t0 = 0;
  var scene = null;
  var gridCanvas = null;
  var starsCanvas = null;
  var matrixCanvas = null;
  var starsCtx = null;
  var matrixCtx = null;
  var gridCtx = null;
  var bodies = {};
  var columns = [];
  var columnKey = "";
  var view = { w: 1, h: 1, low: false, map: null };
  var pointer = { x: 0, y: 0, tx: 0, ty: 0 };

  function hash(n) {
    var x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return x - Math.floor(x);
  }

  function isLow(w) {
    var coarse = window.matchMedia("(pointer: coarse)").matches;
    var save = navigator.connection && navigator.connection.saveData;
    var memory = navigator.deviceMemory && navigator.deviceMemory <= 2;
    return w < 800 || coarse || !!save || !!memory;
  }

  function skyMap() {
    var box = scene.getBoundingClientRect();
    var vw = box.width || window.innerWidth;
    var vh = box.height || window.innerHeight;
    var scale = Math.max(vw / 1600, vh / 900);
    return {
      scale: scale,
      ox: (vw - 1600 * scale) / 2,
      oy: 0,
      w: vw,
      h: vh
    };
  }

  function sizeCanvas(canvas) {
    var dpr = Math.min(window.devicePixelRatio || 1, view.low ? 1.15 : 1.5);
    var w = canvas.clientWidth || window.innerWidth;
    var h = canvas.clientHeight || window.innerHeight;
    var bw = Math.max(1, Math.round(w * dpr));
    var bh = Math.max(1, Math.round(h * dpr));
    if (canvas.width !== bw || canvas.height !== bh) {
      canvas.width = bw;
      canvas.height = bh;
    }
    var ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return ctx;
  }

  function buildDom() {
    scene = document.createElement("div");
    scene.className = "scene";
    scene.setAttribute("aria-hidden", "true");
    scene.innerHTML =
      '<canvas class="scene-stars"></canvas>' +
      '<div class="scene-planets">' +
        '<div class="sky-body sun-glow" data-sky="sun"></div>' +
        '<div class="sky-body planet" data-sky="planet">' +
          '<div class="planet-ring"></div>' +
          '<div class="planet-face">' +
            '<div class="planet-bands"></div>' +
            '<div class="planet-haze"></div>' +
            '<div class="planet-light"></div>' +
            '<div class="planet-lat"></div>' +
          '</div>' +
        '</div>' +
        '<div class="sky-body moon" data-sky="moon">' +
          '<div class="moon-disc"></div>' +
          '<div class="moon-spin"><div class="moon-cut"></div></div>' +
        '</div>' +
      '</div>' +
      '<div class="scene-vignette"></div>' +
      '<canvas class="scene-matrix"></canvas>' +
      '<div class="scene-scan"></div>';

    gridCanvas = document.createElement("canvas");
    gridCanvas.className = "scene-grid";
    gridCanvas.setAttribute("aria-hidden", "true");

    document.body.appendChild(scene);
    document.body.appendChild(gridCanvas);

    starsCanvas = scene.querySelector(".scene-stars");
    matrixCanvas = scene.querySelector(".scene-matrix");
    bodies.sun = scene.querySelector('[data-sky="sun"]');
    bodies.planet = scene.querySelector('[data-sky="planet"]');
    bodies.moon = scene.querySelector('[data-sky="moon"]');
  }

  function placeBody(el, cx, cy, dw, dh, map) {
    var w = dw * map.scale;
    var h = (dh || dw) * map.scale;
    el.style.width = w + "px";
    el.style.height = h + "px";
    el._bx = map.ox + cx * map.scale - w / 2;
    el._by = map.oy + cy * map.scale - h / 2;
  }

  function pullIn(el, map) {
    var w = parseFloat(el.style.width) || 0;
    var visible = 0.58;
    var minX = -w * (1 - visible);
    var maxX = map.w - w * visible;
    if (el._bx < minX) el._bx = minX;
    if (el._bx > maxX) el._bx = maxX;
  }

  function moveBody(el, x, y) {
    el.style.transform = "translate3d(" + (el._bx + x).toFixed(2) + "px," + (el._by + y).toFixed(2) + "px,0)";
  }

  function layout() {
    view.w = scene.clientWidth || window.innerWidth;
    view.h = scene.clientHeight || window.innerHeight;
    view.low = isLow(view.w);
    view.map = skyMap();
    starsCtx = sizeCanvas(starsCanvas);
    matrixCtx = sizeCanvas(matrixCanvas);
    gridCtx = sizeCanvas(gridCanvas);
    placeBody(bodies.planet, 248, 186, 152, 152, view.map);
    placeBody(bodies.moon, 1330, 142, 30, 30, view.map);
    placeBody(bodies.sun, 800, 236, 720, 520, view.map);
    pullIn(bodies.planet, view.map);
    pullIn(bodies.moon, view.map);
    buildColumns();
  }

  function buildColumns() {
    var w = view.w;
    var low = view.low;
    var gap = low ? 34 : 26;
    var keep = low ? 0.55 : 0.5;
    var key = Math.round(w / gap) + ":" + (low ? "l" : "h");
    if (key === columnKey && columns.length) return;
    columnKey = key;
    columns = [];
    var slots = Math.ceil(w / gap);
    var i;
    for (i = 0; i < slots; i += 1) {
      if (hash(i + 1) > keep) continue;
      var seed = hash(i * 3.1 + 9);
      columns.push({
        x: i * gap + gap * 0.35,
        speed: (low ? 16 : 20) + seed * (low ? 28 : 42),
        len: 8 + Math.floor(hash(i + 4) * (low ? 8 : 14)),
        seed: seed * 100,
        origin: hash(i + 8) * view.h,
        magenta: hash(i + 2.2) > 0.8,
        fades: hash(i + 5) > 0.45,
        flick: 1.4 + hash(i + 6) * 4
      });
    }
  }

  function sheetDim(x, w) {
    var band = Math.min(w * 0.62, 430);
    var left = (w - band) / 2;
    var right = left + band;
    var edge = 48;
    if (x < left || x > right) return 1;
    if (x < left + edge) return 1 - 0.55 * ((x - left) / edge);
    if (x > right - edge) return 1 - 0.55 * ((right - x) / edge);
    return 0.42;
  }

  function beat(t) {
    var len = 1.96;
    var phase = (t % len) / len;
    var kick = Math.exp(-phase * 7.5);
    var barPhase = (t % (len * 4)) / (len * 4);
    var bar = Math.exp(-barPhase * 4.5) * 0.45;
    return kick * 0.7 + bar;
  }

  function floorWave(x, z, t) {
    var along = Math.sin(z * 1.45 - t * 1.05 + x * 2.4);
    var across = Math.sin(x * 3.6 - t * 0.55);
    var travel = (t * 0.62) % 18;
    var d = z - travel;
    var packet = Math.exp(-d * d * 0.5) * Math.sin(x * 2.8 + t * 1.8);
    var env = 0.8 + beat(t) * 0.65;
    var disturb = 1 + Math.max(0, pointer.y) * 0.1;
    return (along * 0.62 + across * 0.22 + packet * 0.7) * 0.07 * env * disturb;
  }

  function drawStars(t) {
    var ctx = starsCtx;
    var map = view.map;
    var w = view.w;
    var h = view.h;
    var px = pointer.x * (view.low ? 3 : 5);
    var py = pointer.y * (view.low ? 2 : 3.5);
    var i;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "#f7fbff";
    for (i = 0; i < STARS.length; i += 1) {
      var s = STARS[i];
      var depth = 0.35 + (i % 5) * 0.16;
      var tw = 0.62 + 0.38 * Math.sin(t * (0.45 + (i % 7) * 0.17) + i * 0.7);
      var drift = Math.sin(t * 0.05 + i) * 0.7;
      ctx.globalAlpha = s.a * tw;
      ctx.beginPath();
      ctx.arc(
        map.ox + s.x * map.scale + drift + px * depth,
        map.oy + s.y * map.scale + py * depth,
        Math.max(0.4, s.r * map.scale),
        0,
        Math.PI * 2
      );
      ctx.fill();
    }
    ctx.strokeStyle = "#f4fbff";
    ctx.lineWidth = 1;
    for (i = 0; i < CROSS.length; i += 1) {
      var c = CROSS[i];
      var cx = map.ox + c.x * map.scale + px * 0.5;
      var cy = map.oy + c.y * map.scale + py * 0.5;
      var arm = c.s * map.scale;
      ctx.globalAlpha = 0.35 + 0.4 * (0.5 + 0.5 * Math.sin(t * 0.7 + i * 1.3));
      ctx.beginPath();
      ctx.moveTo(cx - arm, cy);
      ctx.lineTo(cx + arm, cy);
      ctx.moveTo(cx, cy - arm);
      ctx.lineTo(cx, cy + arm);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function drawMatrix(t) {
    var ctx = matrixCtx;
    var w = view.w;
    var h = view.h;
    var low = view.low;
    var font = low ? 12 : 15;
    var step = font + 4;
    var i;
    var n;
    ctx.clearRect(0, 0, w, h);
    ctx.font = font + 'px "IBM Plex Mono", "WenQuanYi Micro Hei Mono", "Noto Sans Mono CJK JP", monospace';
    ctx.textBaseline = "top";
    for (i = 0; i < columns.length; i += 1) {
      var col = columns[i];
      var span = h + col.len * step + 80;
      var head = ((col.origin + t * col.speed) % span) - 20;
      var life = 6.5 + (col.seed % 5);
      var wave = Math.sin((((t * 0.65 + col.seed) % life) / life) * Math.PI);
      var env = col.fades ? wave : 0.45 + 0.55 * wave;
      if (env < 0.04) continue;
      var dim = sheetDim(col.x, w);
      var tick = Math.floor(t * col.flick);
      for (n = 0; n < col.len; n += 1) {
        var y = head - n * step;
        if (y < -step || y > h) continue;
        var fade = 1 - n / col.len;
        var alpha = fade * env * (n === 0 ? 0.62 : 0.32) * dim;
        if (low) alpha *= 0.8;
        if (alpha < 0.012) continue;
        if (col.magenta) {
          ctx.fillStyle = "rgba(255, 79, 216," + alpha.toFixed(3) + ")";
        } else if (n === 0) {
          ctx.fillStyle = "rgba(214, 255, 252," + Math.min(0.34, alpha + 0.04).toFixed(3) + ")";
        } else {
          ctx.fillStyle = "rgba(122, 246, 255," + alpha.toFixed(3) + ")";
        }
        var idx = Math.abs(Math.floor(col.seed * 3 + n * 7 + (n < 2 ? tick : Math.floor(tick / 3)))) % GLYPHS.length;
        ctx.fillText(GLYPHS.charAt(idx), col.x, y);
      }
    }
  }

  function project(x, y, z, vpX, vpY, focal) {
    return {
      x: vpX + (x / z) * focal,
      y: vpY + ((1.15 - y) / z) * focal
    };
  }

  function trace(ctx, pts) {
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    var i;
    for (i = 1; i < pts.length; i += 1) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.stroke();
  }

  function drawRidge(ctx, pts, color, width, alpha, t, vpY, w, h, env) {
    ctx.beginPath();
    var i;
    for (i = 0; i < pts.length; i += 1) {
      var sway = Math.sin(pts[i][0] * 0.012 + t * 0.85) * (1.6 + env * 2.4);
      var x = (pts[i][0] / 1600) * w + pointer.x * 6;
      var y = vpY + (pts[i][1] / 640) * h * 0.34 + sway;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = color;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = width;
    ctx.stroke();
  }

  function drawGrid(t) {
    var ctx = gridCtx;
    var w = view.w;
    var h = view.h;
    var low = view.low;
    var env = beat(t);
    var vpX = w * 0.5 + pointer.x * (low ? 10 : 18);
    var vpY = h * 0.455 + pointer.y * (low ? 5 : 9);
    var focal = h * 0.62;
    var zNear = (1.15 * focal) / Math.max(80, h - vpY + 30);
    var zFar = (1.15 * focal) / 12;
    var rows = low ? 14 : 20;
    var cols = low ? 14 : 24;
    var samplesH = low ? 12 : 22;
    var samplesV = low ? 8 : 14;
    var spacing = (zFar - zNear) / rows;
    var travel = t * 0.55;
    var first = Math.floor(travel / spacing);
    var scroll = travel - first * spacing;
    var xFar = ((w * 0.72) * zNear) / focal;
    var xStep = (xFar * 2) / cols;
    var i;
    var s;
    var z;
    var x;
    var pts;
    var p;
    var fade;
    var alpha;

    ctx.clearRect(0, 0, w, h);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    for (i = 0; i <= cols; i += 1) {
      x = -xFar + i * xStep;
      pts = [];
      for (s = 0; s <= samplesV; s += 1) {
        z = zNear + ((zFar - zNear) * s) / samplesV;
        p = project(x, floorWave(x, z, t), z, vpX, vpY, focal);
        pts.push(p);
      }
      fade = i % 4 === 0 ? 0.42 : 0.22;
      alpha = fade * (0.78 + env * 0.28);
      ctx.strokeStyle = i % 4 === 0 ? "rgba(255, 78, 201," + alpha.toFixed(3) + ")" : "rgba(208, 123, 255," + (alpha * 0.75).toFixed(3) + ")";
      ctx.lineWidth = i % 4 === 0 ? 1.15 : 0.7;
      ctx.globalAlpha = 1;
      trace(ctx, pts);
    }

    for (i = 0; i <= rows; i += 1) {
      z = zNear + i * spacing - scroll;
      if (z < zNear * 0.98) continue;
      pts = [];
      for (s = 0; s <= samplesH; s += 1) {
        x = -xFar + (xFar * 2 * s) / samplesH;
        p = project(x, floorWave(x, z, t), z, vpX, vpY, focal);
        pts.push(p);
      }
      var depth = (z - zNear) / (zFar - zNear);
      var cyan = Math.abs(first + i) % 4 === 0;
      alpha = (0.28 + (1 - depth) * 0.5) * (0.82 + env * 0.35);
      ctx.strokeStyle = cyan ? "rgba(122, 246, 255," + alpha.toFixed(3) + ")" : "rgba(255, 78, 201," + alpha.toFixed(3) + ")";
      ctx.lineWidth = cyan ? 1.35 : 1.05;
      trace(ctx, pts);
    }

    drawRidge(ctx, RIDGE_A, "rgba(255, 138, 224, 0.7)", 1.25, 0.55 + env * 0.15, t, vpY, w, h, env);
    drawRidge(ctx, RIDGE_B, "rgba(122, 246, 255, 0.65)", 1, 0.32 + env * 0.1, t, vpY, w, h, env);

    ctx.globalAlpha = 0.55 + env * 0.2;
    ctx.strokeStyle = "#ff4fd8";
    ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(0, vpY);
    ctx.lineTo(w, vpY);
    ctx.stroke();
    ctx.globalAlpha = 0.4;
    ctx.strokeStyle = "#7af6ff";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, vpY + 3);
    ctx.lineTo(w, vpY + 3);
    ctx.stroke();
    ctx.globalAlpha = 1;
  }

  function updateBodies(t) {
    var amp = view.low ? 0.6 : 1;
    var px = pointer.x;
    var py = pointer.y;
    moveBody(
      bodies.planet,
      (Math.sin(t * 0.075) * 10 + Math.sin(t * 0.019) * 3) * amp + px * 12 * amp,
      Math.cos(t * 0.055) * 5 * amp + py * 6 * amp
    );
    moveBody(
      bodies.moon,
      Math.sin(t * 0.041 + 1.7) * 7 * amp + px * 7 * amp,
      Math.cos(t * 0.033 + 0.4) * 4 * amp + py * 4 * amp
    );
    moveBody(
      bodies.sun,
      Math.sin(t * 0.02) * 3 * amp + px * 4 * amp,
      Math.cos(t * 0.017) * 2 * amp + py * 2 * amp
    );
  }

  function frame(now) {
    if (!running) return;
    raf = 0;
    if (document.hidden) return;
    if (!last) {
      last = now;
      t0 = now;
    }
    var dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    pointer.x += (pointer.tx - pointer.x) * Math.min(1, dt * 2.2);
    pointer.y += (pointer.ty - pointer.y) * Math.min(1, dt * 2.2);
    var t = (now - t0) / 1000;
    if (scene.clientWidth !== view.w || scene.clientHeight !== view.h) layout();
    updateBodies(t);
    drawStars(t);
    drawMatrix(t);
    drawGrid(t);
    raf = window.requestAnimationFrame(frame);
  }

  function onPointer(e) {
    if (e.pointerType === "touch") return;
    pointer.tx = (e.clientX / Math.max(1, window.innerWidth) - 0.5) * 2;
    pointer.ty = (e.clientY / Math.max(1, window.innerHeight) - 0.5) * 2;
  }

  function onLeave() {
    pointer.tx = 0;
    pointer.ty = 0;
  }

  function onVisibility() {
    if (!running) return;
    if (document.hidden) {
      if (raf) window.cancelAnimationFrame(raf);
      raf = 0;
      last = 0;
      return;
    }
    if (!raf) raf = window.requestAnimationFrame(frame);
  }

  function start() {
    if (running || reduceQuery.matches) return;
    running = true;
    buildDom();
    root.classList.add("scene-live");
    layout();
    updateBodies(0);
    drawStars(0);
    drawMatrix(0);
    drawGrid(0);
    if (!booted) {
      window.addEventListener("pointermove", onPointer, { passive: true });
      window.addEventListener("blur", onLeave);
      document.addEventListener("mouseleave", onLeave);
      document.addEventListener("visibilitychange", onVisibility);
      booted = true;
    }
    raf = window.requestAnimationFrame(frame);
  }

  function stop() {
    running = false;
    if (raf) window.cancelAnimationFrame(raf);
    raf = 0;
    last = 0;
    root.classList.remove("scene-live");
    if (scene) scene.remove();
    if (gridCanvas) gridCanvas.remove();
    scene = null;
    gridCanvas = null;
    columns = [];
    columnKey = "";
  }

  if (reduceQuery.addEventListener) {
    reduceQuery.addEventListener("change", function () {
      if (reduceQuery.matches) stop();
      else start();
    });
  }

  try {
    start();
  } catch (err) {
    stop();
    if (window.console && console.error) console.error(err);
  }
})();

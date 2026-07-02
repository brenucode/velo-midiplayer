/* Velo — floating mini-player logic. Fixed layout (no hover-expand). Sizes its
   own window to fit the rendered card, moves on drag, seeks, and drives
   transport through the shared js_api. Live state via window.veloEvent. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const api = () => (window.pywebview && window.pywebview.api) || null;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  let sc = 1, total = 0, rz = null, rzRaf = false;
  const pill = $("pill"), stage = $("stage"), title = $("title"), bar = $("bar");
  const tCur = $("tCur"), tTot = $("tTot"), fill = $("fill"), knob = $("knob");
  const spdVal = $("spdVal"), styleBtn = $("styleBtn");

  const fmt = (s) => { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const STYLE = { faith: "Faithful", bal: "Balanced", easy: "Easy" };
  const fmtSpeed = (pct) => { const x = (pct || 100) / 100; return (Number.isInteger(x) ? x : parseFloat(x.toFixed(2))) + "×"; };

  // cross-fade the title when the track changes
  let titleT = 0;
  function setTitle(name) {
    if (title.textContent === name) return;
    title.style.opacity = "0";
    clearTimeout(titleT);
    titleT = setTimeout(() => { title.textContent = name; title.title = name; title.style.opacity = "1"; }, 140);
  }

  // fade the pill in/out (driven by the backend on show/hide)
  window.veloFade = function (show) { document.body.classList.toggle("shown", !!show); };

  // size the OS window to exactly fit the rendered (scaled) card
  function fitWindow() {
    const r = stage.getBoundingClientRect();
    const a = api();
    if (a && a.overlayResize && r.width > 0) a.overlayResize(Math.ceil(r.width), Math.ceil(r.height));
  }

  function setScale(s) {
    s = clamp(s || 1, 0.7, 1.6);
    if (Math.abs(s - sc) < 0.001) return;
    sc = s;
    document.documentElement.style.setProperty("--sc", sc);
    requestAnimationFrame(fitWindow);
  }

  function applyState(st) {
    if (!st) return;
    setTitle(st.playingName || st.fileName || "Nothing playing");
    document.body.classList.toggle("playing", !!(st.isRunning && !st.paused));
    if (typeof st.speed === "number") spdVal.textContent = fmtSpeed(st.speed);
    styleBtn.textContent = STYLE[st.arrangeMode || "faith"] || "Faithful";
    if (!rz && st.overlay && typeof st.overlay.scale === "number") setScale(st.overlay.scale);
    if (!st.isRunning) setProgress(0, 0);
  }

  function setProgress(cur, tot) {
    total = tot || 0;
    const r = total > 0 ? clamp(cur / total, 0, 1) : 0;
    fill.style.width = knob.style.left = (r * 100) + "%";
    tCur.textContent = fmt(cur); tTot.textContent = fmt(total);
  }

  window.veloEvent = function (ev, payload) {
    if (ev === "state") applyState(payload);
    else if (ev === "timeline") setProgress(payload && payload.current || 0, payload && payload.total || 0);
  };

  // ---- transport ----
  function bind(id, fn) {
    const el = $(id);
    if (el) el.addEventListener("click", (e) => { e.stopPropagation(); const a = api(); if (a) fn(a); });
  }
  bind("ppBtn", (a) => a.toggle && a.toggle());
  bind("prevBtn", (a) => a.prevTrack && a.prevTrack());
  bind("nextBtn", (a) => a.nextTrack && a.nextTrack());
  bind("spdDown", (a) => a.changeSpeed && a.changeSpeed(-5));
  bind("spdUp", (a) => a.changeSpeed && a.changeSpeed(5));
  bind("styleBtn", (a) => a.cyclePlayStyle && a.cyclePlayStyle());
  bind("closeBtn", (a) => a.overlayClose && a.overlayClose());

  // ---- clickable / draggable seek (commit once on release) ----
  let seeking = false, seekRatio = 0;
  function paintSeek(clientX) {
    const r = bar.getBoundingClientRect();
    seekRatio = r.width > 0 ? clamp((clientX - r.left) / r.width, 0, 1) : 0;
    setProgress(seekRatio * total, total);
  }
  bar.addEventListener("pointerdown", (e) => { e.stopPropagation(); seeking = true; try { bar.setPointerCapture(e.pointerId); } catch (_) {} paintSeek(e.clientX); });
  bar.addEventListener("pointermove", (e) => { if (seeking) paintSeek(e.clientX); });
  bar.addEventListener("pointerup", (e) => {
    if (!seeking) return;
    seeking = false; try { bar.releasePointerCapture(e.pointerId); } catch (_) {}
    const a = api(); if (a && a.seek && total > 0) a.seek(Math.round(seekRatio * total));
  });

  // ---- drag to move the window (screen-space deltas → absolute CSS position) ----
  let drag = null, rafPending = false, pendXY = null;
  const isInteractive = (el) => el && el.closest && el.closest("button, .bar, .rz");
  pill.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || isInteractive(e.target)) return;
    drag = { sx: e.screenX, sy: e.screenY, wx: window.screenX, wy: window.screenY };
    try { pill.setPointerCapture(e.pointerId); } catch (_) {}
  });
  pill.addEventListener("pointermove", (e) => {
    if (!drag) return;
    pendXY = [drag.wx + (e.screenX - drag.sx), drag.wy + (e.screenY - drag.sy)];
    if (!rafPending) {
      rafPending = true;
      requestAnimationFrame(() => { rafPending = false; const a = api(); if (a && a.overlayMoveTo && pendXY) a.overlayMoveTo(pendXY[0], pendXY[1]); });
    }
  });
  function endDrag(e) { if (drag) { drag = null; try { pill.releasePointerCapture(e.pointerId); } catch (_) {} } }
  pill.addEventListener("pointerup", endDrag);
  pill.addEventListener("pointercancel", endDrag);

  // ---- resize by dragging the edges / corner (proportional scale) ----
  function applyScaleLive(s) {
    sc = clamp(s, 0.7, 1.6);
    document.documentElement.style.setProperty("--sc", sc);
    if (!rzRaf) { rzRaf = true; requestAnimationFrame(() => { rzRaf = false; fitWindow(); }); }
  }
  document.querySelectorAll(".rz").forEach((el) => {
    el.addEventListener("pointerdown", (e) => {
      if (e.button !== 0) return;
      e.stopPropagation(); e.preventDefault();
      const r = stage.getBoundingClientRect();
      rz = { mode: el.dataset.rz, sx: e.screenX, sy: e.screenY, s0: sc,
             bw: r.width / sc, bh: r.height / sc };
      try { el.setPointerCapture(e.pointerId); } catch (_) {}
    });
    el.addEventListener("pointermove", (e) => {
      if (!rz) return;
      const dx = e.screenX - rz.sx, dy = e.screenY - rz.sy;
      const d = rz.mode === "r" ? dx / rz.bw
              : rz.mode === "b" ? dy / rz.bh
              : Math.max(dx / rz.bw, dy / rz.bh);
      applyScaleLive(rz.s0 + d);
    });
    function stop(e) {
      if (!rz) return; rz = null;
      try { el.releasePointerCapture(e.pointerId); } catch (_) {}
      const a = api(); if (a && a.overlaySetScale) a.overlaySetScale(sc);   // persist
    }
    el.addEventListener("pointerup", stop);
    el.addEventListener("pointercancel", stop);
  });

  // ---- init ----
  function init() {
    const a = api();
    if (a && a.getState) a.getState().then(applyState).catch(() => {});
    requestAnimationFrame(() => { fitWindow(); requestAnimationFrame(fitWindow); });
  }
  if (window.pywebview && window.pywebview.api) init();
  else window.addEventListener("pywebviewready", init);
})();

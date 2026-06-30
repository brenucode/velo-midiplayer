(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  let state = null;
  let scrubbingTotal = 0;
  let scrubDragging = false;

  const api = () => (window.pywebview && window.pywebview.api) || null;

  function call(method, ...args) {
    const a = api();
    if (!a || !a[method]) return Promise.resolve(null);
    return a[method](...args).then((s) => { if (s) applyState(s); return s; });
  }

  // ---------- Python -> JS events ----------
  window.veloEvent = function (event, payload) {
    if (event === "state") applyState(payload);
    else if (event === "log") {
      const el = logEl(payload.target || "player");
      payload.lines.forEach((l) => appendLog(el, l));
    }
    else if (event === "timeline") updateTimeline(payload);
    else if (event === "drumsState") applyDrumsState(payload);
    else if (event === "drumsTimeline") updateDrumsTimeline(payload);
    else if (event === "inputState") applyInputState(payload);
    else if (event === "inputNote") { /* reserved for future visual keyboard */ }
    else if (event === "notes") payload.events.forEach(handleNote);
    else if (event === "update") showUpdate(payload);
  };

  let updateInfo = null;
  function showUpdate(p) {
    if (!p || !p.newer) return;
    updateInfo = p;
    const t = $("#updateToast"); if (!t) return;
    const ver = $("#utVer"); if (ver) ver.textContent = "v" + (p.latest || "");
    const dl = $("#utDl"); if (dl) { dl.disabled = false; dl.textContent = "Download"; }
    const notes = $("#utNotes"); if (notes) notes.style.display = p.url ? "" : "none";
    const sub = $("#utSub"); if (sub) sub.textContent = "A newer version of Velo is out.";
    t.hidden = false;
  }

  // Keep the Creator avatar in sync with the live Discord profile picture.
  // Discord's CDN needs the current avatar *hash* (which changes when you swap
  // your pic); we resolve it by user id through Lanyard (no bot/token). Needs
  // the account to be a member of discord.gg/lanyard; otherwise the static
  // image stays as a fallback.
  function refreshDiscordAvatar() {
    const img = document.getElementById("creditAvatar");
    if (!img || !img.dataset.discord) return;
    const id = img.dataset.discord;
    fetch("https://api.lanyard.rest/v1/users/" + id)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const u = d && d.success && d.data && d.data.discord_user;
        if (!u || !u.avatar) return;
        const ext = String(u.avatar).startsWith("a_") ? "gif" : "png";
        img.src = "https://cdn.discordapp.com/avatars/" + id + "/" + u.avatar + "." + ext + "?size=160";
      })
      .catch(() => {});
  }

  // ---------- SOUND (mic illusion) ----------
  let soundOn = false, soundMode = "piano";
  let audioCtx = null, masterGain = null, limiter = null, piano = null;
  // The soundfont samples are mastered quiet, so we run the master bus hot at a
  // fixed 3x, with a limiter right after it so the extra loudness never clips —
  // even on a full chord. There's no in-app volume slider on purpose: people set
  // Velo's loudness from the Windows volume mixer (it controls this app's own
  // audio output directly), which is the natural place for it.
  const PIANO_GAIN = 3.0;
  const activeNotes = {};

  // Selectable piano models (MusyngKite soundfonts, bundled locally — fuller and
  // more realistic than the old FluidR3 grand).
  const PIANOS = [
    { id: "grand", inst: "acoustic_grand_piano", label: "Grand Piano" },
    { id: "bright", inst: "bright_acoustic_piano", label: "Bright Piano" },
    { id: "electric", inst: "electric_piano_1", label: "Electric Piano" },
    { id: "egrand", inst: "electric_grand_piano", label: "Electric Grand" },
  ];
  let currentPianoId = "grand";
  let pianoLoadingId = null;
  const pianoInsts = {};

  // Online keyboard sound library (Mechvibes packs via jsdelivr CDN).
  const MECH = "https://cdn.jsdelivr.net/gh/hainguyents13/mechvibes@2.3.6/src/audio/";
  const PACKS = [
    { id: "brown-local", label: "Cherry MX Brown (default · offline)", local: true },
    { id: "cherrymx-black-abs", label: "Cherry MX Black", base: MECH + "cherrymx-black-abs/" },
    { id: "cherrymx-blue-abs", label: "Cherry MX Blue", base: MECH + "cherrymx-blue-abs/" },
    { id: "cherrymx-brown-abs", label: "Cherry MX Brown (ABS)", base: MECH + "cherrymx-brown-abs/" },
    { id: "cherrymx-red-abs", label: "Cherry MX Red", base: MECH + "cherrymx-red-abs/" },
    { id: "cherrymx-black-pbt", label: "Cherry MX Black · PBT", base: MECH + "cherrymx-black-pbt/" },
    { id: "cherrymx-blue-pbt", label: "Cherry MX Blue · PBT", base: MECH + "cherrymx-blue-pbt/" },
    { id: "cherrymx-brown-pbt", label: "Cherry MX Brown · PBT", base: MECH + "cherrymx-brown-pbt/" },
    { id: "cherrymx-red-pbt", label: "Cherry MX Red · PBT", base: MECH + "cherrymx-red-pbt/" },
  ];
  const packData = {};
  let currentPackId = "brown-local";

  // a synthesized impulse response for a subtle room reverb — this is what makes
  // the sampled piano stop sounding flat/"MIDI" and feel like a real room.
  function makeImpulse(dur, decay) {
    const rate = audioCtx.sampleRate, len = Math.max(1, Math.floor(rate * dur));
    const buf = audioCtx.createBuffer(2, len, rate);
    for (let c = 0; c < 2; c++) {
      const d = buf.getChannelData(c);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, decay);
    }
    return buf;
  }

  function ensureCtx(minGain) {
    if (!audioCtx) {
      try {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        masterGain = audioCtx.createGain();
        masterGain.gain.value = PIANO_GAIN;
        // brick-wall-ish limiter on the master bus: lets us push volume past 1.0
        // for real loudness while catching peaks so chords don't clip/distort.
        limiter = audioCtx.createDynamicsCompressor();
        limiter.threshold.value = -2.0;
        limiter.knee.value = 0;
        limiter.ratio.value = 20;
        limiter.attack.value = 0.003;
        limiter.release.value = 0.25;
        limiter.connect(audioCtx.destination);
        masterGain.connect(limiter);
        try {
          const conv = audioCtx.createConvolver();
          conv.buffer = makeImpulse(2.4, 2.6);
          const wet = audioCtx.createGain(); wet.gain.value = 0.18;
          masterGain.connect(conv); conv.connect(wet); wet.connect(limiter);
        } catch (_) {}
      } catch (e) { return; }
    }
    if (audioCtx.state === "suspended") audioCtx.resume();
    if (minGain && masterGain && masterGain.gain.value < minGain) masterGain.gain.value = minGain;
  }

  function ensureAudio() {
    ensureCtx();
    if (!audioCtx) return;
    if (soundMode === "piano") loadPiano(); else loadPack(currentPackId);
  }

  function loadPiano() {
    const p = PIANOS.find((x) => x.id === currentPianoId) || PIANOS[0];
    if (pianoInsts[p.id]) { piano = pianoInsts[p.id]; return; }
    if (pianoLoadingId === p.id || !window.Soundfont || !audioCtx) return;
    pianoLoadingId = p.id;
    window.Soundfont.instrument(audioCtx, p.inst, {
      destination: masterGain,
      nameToUrl: () => `audio/mk_${p.inst}-mp3.js`,
    }).then((inst) => {
      pianoInsts[p.id] = inst;
      if (currentPianoId === p.id) piano = inst;
      pianoLoadingId = null;
    }).catch(() => { pianoLoadingId = null; });
  }

  function setPiano(id) {
    if (!PIANOS.some((p) => p.id === id)) return;
    currentPianoId = id;
    piano = pianoInsts[id] || null;   // synth fallback until the model loads
    if (audioCtx) loadPiano();
  }

  function setPackStatus(id, state) {
    if (id !== currentPackId) return;
    const el = $("#packStatus"); if (!el) return;
    el.textContent = state === "loading" ? "loading…" : state === "failed" ? "couldn't load" : "";
  }

  // Loads a keyboard sound pack (local bundled, or online sprite from the CDN).
  function loadPack(id) {
    const existing = packData[id];
    if (existing && (existing.buffer || existing.loading)) {
      setPackStatus(id, existing.buffer ? "ready" : "loading");
      return;
    }
    const pack = PACKS.find((p) => p.id === id);
    if (!pack || !audioCtx) return;
    packData[id] = { loading: true };
    setPackStatus(id, "loading");
    const cfgUrl = pack.local ? "audio/brown-config.json" : pack.base + "config.json";
    fetch(cfgUrl).then((r) => r.json()).then((cfg) => {
      if ((cfg.key_define_type || "single") !== "single") throw new Error("unsupported pack type");
      const segs = Object.values(cfg.defines || {}).filter((s) => Array.isArray(s) && s.length >= 2);
      const oggUrl = pack.local ? "audio/brown.ogg" : pack.base + (cfg.sound || "sound.ogg");
      return fetch(oggUrl).then((r) => r.arrayBuffer()).then((ab) => audioCtx.decodeAudioData(ab)).then((buf) => {
        packData[id] = { buffer: buf, segs: segs };
        setPackStatus(id, "ready");
      });
    }).catch(() => { packData[id] = { failed: true }; setPackStatus(id, "failed"); });
  }

  // Play a random key segment from the selected pack's sprite buffer.
  function playKeySound(velocity, isDown) {
    if (!audioCtx) return;
    const pd = packData[currentPackId];
    if (pd && pd.buffer && pd.segs && pd.segs.length) {
      const seg = pd.segs[(Math.random() * pd.segs.length) | 0];
      const src = audioCtx.createBufferSource();
      src.buffer = pd.buffer;
      const g = audioCtx.createGain();
      g.gain.value = Math.min(1, (velocity / 127) * 0.8 + 0.2) * (isDown ? 1 : 0.45);
      src.connect(g).connect(masterGain);
      src.onended = () => { try { src.disconnect(); g.disconnect(); } catch (_) {} };
      try { src.start(audioCtx.currentTime, seg[0] / 1000, seg[1] / 1000); }
      catch (_) { try { src.start(); } catch (e) {} }
      return;
    }
    playSynthKey(velocity, isDown);  // fallback while the pack loads
  }

  // Synth fallback (used only until the real Cherry MX Brown sample loads).
  function playSynthKey(velocity, isDown) {
    if (!audioCtx) return;
    const now = audioCtx.currentTime;
    const amp = (Math.min(1, (velocity / 127) * 0.7 + 0.18)) * (isDown ? 1 : 0.45);

    // body thock (the keycap bottoming/topping out)
    const osc = audioCtx.createOscillator();
    osc.type = "sine";
    const f0 = (isDown ? 190 : 240) + Math.random() * 40;
    osc.frequency.setValueAtTime(f0, now);
    osc.frequency.exponentialRampToValueAtTime(f0 * 0.5, now + 0.05);
    const oG = audioCtx.createGain();
    oG.gain.setValueAtTime(amp * 0.55, now);
    oG.gain.exponentialRampToValueAtTime(0.001, now + (isDown ? 0.07 : 0.045));
    osc.connect(oG).connect(masterGain);
    osc.onended = () => { try { osc.disconnect(); oG.disconnect(); } catch (_) {} };
    osc.start(now); osc.stop(now + 0.1);

    // contact transient — low-passed so it's a "thock", not a sharp click
    const dur = isDown ? 0.028 : 0.018;
    const n = Math.floor(audioCtx.sampleRate * dur);
    const buf = audioCtx.createBuffer(1, n, audioCtx.sampleRate);
    const d = buf.getChannelData(0);
    for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / n, 2);
    const src = audioCtx.createBufferSource();
    src.buffer = buf;
    const lp = audioCtx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 1100 + Math.random() * 500;
    const nG = audioCtx.createGain();
    nG.gain.setValueAtTime(amp * 0.5, now);
    nG.gain.exponentialRampToValueAtTime(0.001, now + dur);
    src.connect(lp).connect(nG).connect(masterGain);
    src.onended = () => { try { src.disconnect(); lp.disconnect(); nG.disconnect(); } catch (_) {} };
    src.start(now); src.stop(now + dur + 0.01);
  }

  // Synth piano fallback (used when real samples can't load, e.g. CDN blocked)
  function playSynthPiano(n, velocity) {
    const now = audioCtx.currentTime;
    const freq = 440 * Math.pow(2, (n - 69) / 12);
    const amp = Math.min(0.5, (velocity / 127) * 0.4 + 0.05);
    const o1 = audioCtx.createOscillator(); o1.type = "triangle"; o1.frequency.value = freq;
    const o2 = audioCtx.createOscillator(); o2.type = "sine"; o2.frequency.value = freq * 2;
    const g = audioCtx.createGain();
    g.gain.setValueAtTime(0.0001, now);
    g.gain.exponentialRampToValueAtTime(amp, now + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, now + 1.8);
    const g2 = audioCtx.createGain(); g2.gain.value = 0.3;
    o1.connect(g); o2.connect(g2).connect(g); g.connect(masterGain);
    o1.start(now); o2.start(now); o1.stop(now + 2.0); o2.stop(now + 2.0);
    return {
      stop(t) {
        const at = t || audioCtx.currentTime;
        try {
          g.gain.cancelScheduledValues(at);
          g.gain.setTargetAtTime(0.0001, at, 0.08);
          o1.stop(at + 0.4); o2.stop(at + 0.4);
        } catch (_) {}
      },
    };
  }

  function handleNote(p) {
    if (!soundOn || !audioCtx) return;
    if (soundMode === "keyboard") {
      playKeySound(p.v, p.on);   // sound on both press and release, like real typing
      return;
    }
    if (p.on) {
      try { if (activeNotes[p.n]) activeNotes[p.n].stop(); } catch (_) {}
      try {
        activeNotes[p.n] = piano
          ? piano.play(p.n, audioCtx.currentTime, { gain: Math.max(0.05, p.v / 127) })
          : playSynthPiano(p.n, p.v);
      } catch (_) {}
    } else if (activeNotes[p.n]) {
      try { activeNotes[p.n].stop(audioCtx.currentTime); } catch (_) {}
      delete activeNotes[p.n];
    }
  }

  function stopAllNotes() {
    Object.keys(activeNotes).forEach((n) => {
      try { activeNotes[n].stop(); } catch (_) {}
      delete activeNotes[n];
    });
  }

  const HUM_KEYS = ["roll", "timing", "rubato", "velocity"];
  const humId = (k) => "hum" + k[0].toUpperCase() + k.slice(1);

  function applyHumanizeState(h) {
    if (!h) return;
    const on = !!h.on;
    const prof = on ? (h.profile || "custom") : "off";
    $$("#humProfile .seg-opt").forEach((o) => o.classList.toggle("active", o.dataset.hum === prof));
    const box = $("#humSliders");
    if (box) { box.style.opacity = on ? "1" : ".4"; box.style.pointerEvents = on ? "" : "none"; }
    HUM_KEYS.forEach((k) => {
      const el = $("#" + humId(k));
      if (el && typeof h[k] === "number") {
        el.value = h[k];
        el.style.setProperty("--fill", h[k] + "%");
        const lab = $("#" + humId(k) + "Val"); if (lab) lab.textContent = h[k];
      }
    });
  }

  const RF_KEYS = [["speed", "rfSpeed"], ["transpose", "rfTranspose"]];

  function applyRandomFailState(rf) {
    if (!rf) return;
    const on = !!rf.enabled;
    const t = $("#rfToggle");
    if (t) { t.textContent = on ? "On" : "Off"; t.classList.toggle("on", on); }
    const box = $("#rfSliders");
    if (box) { box.style.opacity = on ? "1" : ".4"; box.style.pointerEvents = on ? "" : "none"; }
    RF_KEYS.forEach(([k, id]) => {
      const el = $("#" + id);
      if (el && typeof rf[k] === "number") {
        const v = Math.round(rf[k]);
        el.value = v;
        el.style.setProperty("--fill", v + "%");
        const lab = $("#" + id + "Val"); if (lab) lab.textContent = v;
      }
    });
  }

  function applySoundState(s) {
    if (!s) return;
    soundOn = !!s.enabled;
    soundMode = s.mode === "keyboard" ? "keyboard" : "piano";
    const t = $("#soundToggle");
    if (t) { t.textContent = soundOn ? "On" : "Off"; t.classList.toggle("on", soundOn); }
    $$("#soundMode .seg-opt").forEach((o) => o.classList.toggle("active", o.dataset.smode === soundMode));

    currentPackId = s.pack || "brown-local";
    const packSel = $("#soundPack");
    if (packSel) {
      if (!packSel.options.length) PACKS.forEach((p) => { const o = document.createElement("option"); o.value = p.id; o.textContent = p.label; packSel.appendChild(o); });
      packSel.value = currentPackId;
    }
    const packRow = $("#soundPackRow"); if (packRow) packRow.hidden = soundMode !== "keyboard";
    setPackStatus(currentPackId, packData[currentPackId] && packData[currentPackId].buffer ? "ready" : "");

    const pid = s.piano || "grand";
    if (pid !== currentPianoId) setPiano(pid); else currentPianoId = pid;
    const pSel = $("#prPianoSel");
    if (pSel) {
      if (!pSel.options.length) PIANOS.forEach((p) => { const o = document.createElement("option"); o.value = p.id; o.textContent = p.label; pSel.appendChild(o); });
      pSel.value = currentPianoId;
    }

    if (soundOn) ensureAudio(); else stopAllNotes();
  }

  const LOG_EL = { player: "#log", drums: "#drumsLog", input: "#inputLog" };
  function logEl(target) { return $(LOG_EL[target] || "#log"); }

  // ---------- formatting ----------
  function fmt(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  // ---------- state rendering ----------
  function applyState(s) {
    if (!s) return;
    state = s;

    $("#fileName").textContent = s.fileName || "No file selected";
    $("#fileSub").textContent = s.fileName
      ? s.currentFile
      : "Choose a .mid or .midi file to start";

    const rec = $("#recentSelect");
    rec.innerHTML = "";
    if (s.recentFiles && s.recentFiles.length) {
      const ph = document.createElement("option");
      ph.value = ""; ph.textContent = "Recent…"; ph.disabled = true; ph.selected = !s.currentFile;
      rec.appendChild(ph);
      s.recentFiles.forEach((f) => {
        const o = document.createElement("option");
        o.value = f.path; o.textContent = f.name;
        if (f.path === s.currentFile) o.selected = true;
        rec.appendChild(o);
      });
      rec.style.display = "";
    } else {
      rec.style.display = "none";
    }

    setPlaying(s.isRunning, s.paused, s.selectedIsPlaying);
    $("#stopBtn").disabled = !s.isRunning;

    const showNow = s.isRunning && s.playingFile && s.playingFile !== s.currentFile;
    const nb = $("#nowBar");
    if (showNow) { $("#nowName").textContent = s.playingName; nb.hidden = false; }
    else nb.hidden = true;

    if (s.isRunning && s.totalSeconds) scrubbingTotal = s.totalSeconds;
    if ("onTop" in s) $("#winPin").classList.toggle("on", !!s.onTop);
    if (s.sound) applySoundState(s.sound);
    if (s.humanize) applyHumanizeState(s.humanize);
    if (s.randomFail) applyRandomFailState(s.randomFail);

    if (queueVisible() && !queueDragging) renderQueue();

    setSpeedUI(s.speed);

    $$("#chips .chip").forEach((c) => {
      const on = !!(s.options && s.options[c.dataset.opt]);
      c.classList.toggle("on", on);
    });

    const midi = !!(s.options && s.options.useMIDIOutput);
    setMode(midi ? "midi" : "qwerty", false);
    $("#deviceRow").hidden = !midi;
    const dev = $("#deviceSelect");
    dev.innerHTML = "";
    (s.outputDevices || []).forEach((d) => {
      const o = document.createElement("option");
      o.value = d; o.textContent = d;
      if (d === s.outputDevice) o.selected = true;
      dev.appendChild(o);
    });

    if (!s.isRunning) {
      $("#tTot").textContent = s.totalText || "0:00:00";
      $("#tCur").textContent = "0:00:00";
      setScrub(0);
      stopAllNotes();
    }

    if (sgOpen) stageStateChanged();
  }

  function setPlaying(running, paused, selectedIsPlaying) {
    const app = $("#app");
    app.classList.toggle("playing", running && !paused);
    const ico = $("#playIco");
    const showPause = running && !paused && selectedIsPlaying;
    if (showPause) {
      ico.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24"><rect x="6" y="5" width="4" height="14" rx="1.4" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1.4" fill="currentColor"/></svg>';
      $("#playBtn").setAttribute("aria-label", "Pause");
    } else {
      ico.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M8 5v14l11-7-11-7z" fill="currentColor"/></svg>';
      $("#playBtn").setAttribute("aria-label",
        running && !selectedIsPlaying ? "Play selected" : (running ? "Resume" : "Play"));
    }
  }

  function setSpeedUI(v) {
    const sl = $("#speedSlider"), inp = $("#speedInput");
    sl.value = Math.min(300, Math.max(10, v));
    inp.value = v;
    const pct = ((sl.value - sl.min) / (sl.max - sl.min)) * 100;
    sl.style.setProperty("--fill", pct + "%");
  }

  function updateTimeline(p) {
    scrubbingTotal = p.total || scrubbingTotal;
    if (sgOpen) stageSync(p.current);
    if (scrubDragging) return;
    const parts = (p.text || "").split(" / ");
    $("#tCur").textContent = parts[0] || fmt(p.current);
    $("#tTot").textContent = parts[1] || fmt(p.total);
    setScrub(p.total ? (p.current / p.total) : 0);
  }

  function setScrub(ratio) {
    ratio = Math.max(0, Math.min(1, ratio));
    $("#scrubFill").style.width = (ratio * 100) + "%";
    $("#scrubDot").style.left = (ratio * 100) + "%";
  }

  // ---------- console ----------
  function appendLog(log, line) {
    if (!log) return;
    const div = document.createElement("div");
    div.className = "ln";
    div.textContent = line;
    log.appendChild(div);
    while (log.children.length > 300) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;
  }

  // ---------- nav ----------
  function switchView(name) {
    const prev = (document.querySelector(".nav.active") || {}).dataset
      ? document.querySelector(".nav.active").dataset.view : null;
    if (prev === "practice" && name !== "practice") prLeave();

    $$(".nav").forEach((n) => n.classList.toggle("active", n.dataset.view === name));
    $$(".view").forEach((v) => { v.hidden = v.dataset.view !== name; });
    const a0 = api(); if (a0 && a0.setLastView) a0.setLastView(name);
    if (name === "hub" && !hubLoaded) loadHub();
    else if (name === "queue") renderQueue();
    else if (name === "practice") prEnter();
    else if (name === "drums") { const a = api(); if (a && a.drumsState) a.drumsState().then(applyDrumsState); }
    else if (name === "keys") { const a = api(); if (a && a.inputState) a.inputState().then(applyInputState); }
    else if (name === "settings") { const a = api(); if (a && a.getState) a.getState().then((s) => applyHotkeys(s.hotkeys)); }
  }

  // ---------- MIDI Hub ----------
  let hubData = [], hubFiltered = [], hubPage = 1, hubLoaded = false;
  let hubSource = "nanomidi";
  let bitQuery = "", bitPage = 0, bitTotal = 0, bitPageSize = 15;
  const HUB_PAGE_SIZE = 12;

  function loadHub() {
    if (hubSource === "bitmidi") { loadBit($("#hubSearch").value); return; }
    if (hubSource === "onlineseq") { loadOnlineSeq($("#hubSearch").value); return; }
    // nanoMIDI (Python backend) — works only when their server is up
    hubLoaded = true;
    const a = api();
    if (!a || !a.hubList) return;
    showHubState('<div class="spinner"></div><p>Loading library…</p>');
    a.hubList().then((res) => {
      if (!res || !res.ok) {
        hubLoaded = false;
        showHubState('<p>The nanoMIDI library server isn\'t responding right now.\nThat\'s their service, not your connection — try again, or switch the source to BitMidi above.</p><button class="btn" id="hubRetry" style="margin-top:4px">Try again</button>');
        const rb = document.getElementById("hubRetry");
        if (rb) rb.addEventListener("click", loadHub);
        return;
      }
      hubData = res.items || [];
      applyHubFilter();
    });
  }

  function cleanName(s) {
    return String(s || "").replace(/\.midi?$/i, "").replace(/[_]+/g, " ").trim();
  }

  // BitMidi: searched via the Python backend (needs a browser User-Agent to get
  // past Cloudflare; the proxy serves it fine that way).
  function loadBit(query, page) {
    hubLoaded = true;
    if (query !== undefined && query !== null) bitQuery = (query || "").trim();
    bitPage = Math.max(0, page || 0);
    showHubState('<div class="spinner"></div><p>Searching BitMidi…</p>');
    const a = api();
    if (!a || !a.hubSearchBit) { showHubState('<p>BitMidi unavailable.</p>'); return; }
    a.hubSearchBit(bitQuery, bitPage).then((res) => {
      if (!res || !res.ok) {
        showHubState('<p>Couldn\'t reach BitMidi right now.\nTry again in a moment.</p><button class="btn" id="hubRetry" style="margin-top:4px">Try again</button>');
        const rb = document.getElementById("hubRetry"); if (rb) rb.addEventListener("click", loadHub);
        return;
      }
      bitTotal = res.total || 0;
      bitPageSize = res.pageSize || 15;
      const raw = res.items || [];
      if (!raw.length) { showHubState('<p>No results on BitMidi for "' + esc(bitQuery || "piano") + '".</p>'); return; }
      hubFiltered = raw.map((x) => ({
        name: cleanName(x.name),
        artists: "BitMidi",
        arranger: "",
        downloads: x.downloads || 0,
        image: "",
        source: "bitmidi",
        downloadUrl: x.downloadUrl,
      }));
      renderHub();
    });
  }

  // Online Sequencer: the whole site is behind Cloudflare, so the Python side
  // drives a hidden, challenge-cleared WebView2 to fetch + parse results and to
  // run the site's own exportMidi() on download. First search waits for the
  // challenge to clear (~10s); after that it's quick.
  function loadOnlineSeq(query) {
    hubLoaded = true;
    const a = api();
    if (!a || !a.osSearch) { showHubState('<p>Online Sequencer unavailable.</p>'); return; }
    showHubState('<div class="spinner"></div><p>Reaching Online Sequencer…\n<small style="opacity:.6">the first search runs a one-time check in the background (~15s); after that it\'s instant</small></p>');
    a.osSearch((query || "").trim()).then((res) => {
      if (!res || !res.ok) {
        const msg = res && res.needWindow
          ? "Couldn't get past Online Sequencer's check automatically.\nA window may have opened — solve it once, then try again."
          : "Couldn't reach Online Sequencer right now.\nTry again in a moment.";
        showHubState('<p>' + esc(msg).replace(/\n/g, "<br>") + '</p><button class="btn" id="hubRetry" style="margin-top:4px">Try again</button>');
        const rb = document.getElementById("hubRetry"); if (rb) rb.addEventListener("click", loadHub);
        return;
      }
      hubData = (res.items || []).map((x) => ({
        id: x.id,
        name: cleanName(x.title) || ("Sequence " + x.id),
        artists: "Online Sequencer",
        arranger: "",
        downloads: 0,
        notes: x.notes || "",
        image: "",
        source: "onlineseq",
      }));
      if (!hubData.length) { showHubState('<p>No results on Online Sequencer for "' + esc((query || "").trim() || "featured") + '".</p>'); return; }
      hubFiltered = hubData; hubPage = 1; renderHub();
    });
  }

  function showHubState(html) {
    const s = $("#hubState");
    s.hidden = false; s.innerHTML = html;
    $("#hubList").hidden = true;
    $("#hubPager").hidden = true;
  }

  function applyHubFilter() {
    const q = ($("#hubSearch").value || "").toLowerCase();
    const sort = $("#hubSort").value;
    let list = hubData.filter((m) =>
      q === "" || m.name.toLowerCase().includes(q) || m.artists.toLowerCase().includes(q));
    if (sort === "Oldest") list.sort((a, b) => a.id - b.id);
    else if (sort === "Newest") list.sort((a, b) => b.id - a.id);
    else if (sort === "Downloads") list.sort((a, b) => (b.downloads || 0) - (a.downloads || 0));
    else if (sort === "Views") list.sort((a, b) => (b.views || 0) - (a.views || 0));
    hubFiltered = list;
    hubPage = 1;
    renderHub();
  }

  function hubTotalPages() {
    if (hubSource === "bitmidi") return Math.max(1, Math.ceil(bitTotal / (bitPageSize || 15)));
    return Math.max(1, Math.ceil(hubFiltered.length / HUB_PAGE_SIZE));
  }

  function renderHub() {
    let slice, pageNum;
    const totalPages = hubTotalPages();
    if (hubSource === "bitmidi") {
      slice = hubFiltered;          // current server page (already 15 items)
      pageNum = bitPage + 1;
    } else {
      hubPage = Math.min(hubPage, totalPages);
      const start = (hubPage - 1) * HUB_PAGE_SIZE;
      slice = hubFiltered.slice(start, start + HUB_PAGE_SIZE);
      pageNum = hubPage;
    }

    const list = $("#hubList");
    $("#hubState").hidden = true;
    list.hidden = false;
    list.innerHTML = "";

    if (!slice.length) { showHubState('<p>No results found.</p>'); return; }

    slice.forEach((m, i) => {
      const card = document.createElement("div");
      card.className = "hub-card";
      card.style.setProperty("--i", i);
      const extra = m.arranger ? `<span>Arr: ${esc(m.arranger)}</span>` : "";
      const meta = m.source === "onlineseq"
        ? (m.notes ? `<span>${esc(m.notes)}</span>` : "")
        : `<span>↓ ${m.downloads || 0}</span>`;
      card.innerHTML =
        (m.image ? `<img class="hub-thumb" src="${esc(m.image)}" loading="lazy" alt="" onerror="this.style.visibility='hidden'"/>` : `<div class="hub-thumb"></div>`) +
        `<div class="hub-info">
           <div class="hub-name">${esc(m.name)}</div>
           <div class="hub-artist">${esc(m.artists)}</div>
           <div class="hub-extra">${extra}${meta}</div>
         </div>
         <button class="hub-dl" title="Download and load" aria-label="Download">
           <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9"><path d="M12 4v11m0 0 4-4m-4 4-4-4"/><path d="M5 19h14"/></svg>
         </button>`;
      card.querySelector(".hub-dl").addEventListener("click", () => hubDownload(m, card));
      list.appendChild(card);
    });

    $("#hubPager").hidden = false;
    $("#hubPageLabel").textContent = `Page ${pageNum}/${totalPages}`;
    $("#hubPrev").disabled = pageNum <= 1;
    $("#hubNext").disabled = pageNum >= totalPages;
    const content = document.querySelector(".content"); if (content) content.scrollTop = 0;
  }

  function abToBase64(buf) {
    let bin = ""; const bytes = new Uint8Array(buf);
    for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin);
  }

  function hubDownload(m, card) {
    const btn = card.querySelector(".hub-dl");
    btn.innerHTML = '<div class="spinner" style="width:16px;height:16px;border-width:2px"></div>';
    const ok = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="m5 13 4 4L19 7"/></svg>';
    const done = (res) => {
      btn.innerHTML = ok;
      if (res && res.ok && res.state) { applyState(res.state); setTimeout(() => switchView("player"), 450); }
    };
    if (m.source === "bitmidi") {
      api().hubDownloadBit(m.downloadUrl, m.name).then(done).catch(() => { btn.textContent = "!"; });
      return;
    }
    if (m.source === "onlineseq") {
      api().osDownload(m.id, m.name).then((res) => {
        if (res && res.ok) { done(res); }
        else { btn.textContent = "!"; btn.title = (res && res.error) || "failed"; }
      }).catch(() => { btn.textContent = "!"; });
      return;
    }
    if (!m.midiFilename) return;
    api().hubDownload(m.midiFilename).then(done);
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------- QUEUE ----------
  function queueVisible() {
    const qv = document.querySelector('.view[data-view="queue"]');
    return qv && !qv.hidden;
  }

  let queueDragging = false;
  let dragFromIndex = -1;

  function renderQueue() {
    const list = $("#queueList"), empty = $("#queueEmpty");
    const files = (state && state.recentFiles) || [];
    list.innerHTML = "";
    if (!files.length) { empty.hidden = false; list.hidden = true; return; }
    empty.hidden = true; list.hidden = false;
    files.forEach((f, i) => {
      const isPlaying = state.isRunning && f.path === state.playingFile;
      const isSel = f.path === state.currentFile;
      const row = document.createElement("div");
      row.className = "queue-row" + (isPlaying ? " playing" : "");
      row.draggable = true;
      row.dataset.index = i;
      row.innerHTML =
        '<span class="queue-grip" aria-hidden="true"><svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor"><circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/><circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/><circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/></svg></span>' +
        (isPlaying
          ? '<span class="queue-num"><span class="queue-eq"><i></i><i></i><i></i></span></span>'
          : `<span class="queue-num">${i + 1}</span>`) +
        `<span class="queue-name">${esc(f.name)}</span>` +
        (isSel && !isPlaying ? '<span class="queue-tag sel">selected</span>' : "") +
        `<span class="queue-act">
           <button class="q-btn play" title="Play" aria-label="Play"><svg viewBox="0 0 24 24" width="16" height="16"><path d="M8 5v14l11-7-11-7z" fill="currentColor"/></svg></button>
           <button class="q-btn del" title="Remove" aria-label="Remove"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg></button>
         </span>`;
      row.querySelector(".q-btn.play").addEventListener("click", (e) => { e.stopPropagation(); call("playPath", f.path); });
      row.querySelector(".q-btn.del").addEventListener("click", (e) => { e.stopPropagation(); call("removeFromQueue", f.path); });
      row.addEventListener("click", () => call("playPath", f.path));

      row.addEventListener("dragstart", (e) => {
        queueDragging = true; dragFromIndex = i;
        row.classList.add("dragging-row");
        try { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); } catch (_) {}
      });
      row.addEventListener("dragover", (e) => { e.preventDefault(); e.stopPropagation(); row.classList.add("drag-over"); });
      row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
      row.addEventListener("drop", (e) => {
        e.preventDefault(); e.stopPropagation();
        row.classList.remove("drag-over");
        const from = dragFromIndex, to = i;
        queueDragging = false; dragFromIndex = -1;
        if (from === -1 || from === to) return;
        const arr = files.slice();
        const [moved] = arr.splice(from, 1);
        arr.splice(to, 0, moved);
        call("reorderQueue", arr.map((x) => x.path));
      });
      row.addEventListener("dragend", () => {
        queueDragging = false; dragFromIndex = -1;
        $$(".queue-row").forEach((r) => r.classList.remove("drag-over", "dragging-row"));
      });

      list.appendChild(row);
    });
  }

  // ---------- mode switch ----------
  function setMode(mode, persist) {
    const sw = $("#modeSwitch");
    const opts = $$(".mode-opt", sw) ;
    const active = sw.querySelector(`.mode-opt[data-mode="${mode}"]`);
    if (!active) return;
    $$(".mode-opt").forEach((o) => o.classList.toggle("active", o === active));
    const glider = $(".mode-glider");
    glider.style.width = active.offsetWidth + "px";
    glider.style.transform = `translateX(${active.offsetLeft - 3}px)`;
    if (persist) call("setOption", "useMIDIOutput", mode === "midi");
  }

  // ---------- DRUMS ----------
  let drumsState = null;
  function applyDrumsState(s) {
    if (!s) return;
    drumsState = s;
    $("#drumsFileName").textContent = s.fileName || "No file selected";
    $("#drumsFileSub").textContent = s.fileName ? s.currentFile : "Choose a drums .mid file";
    const rec = $("#drumsRecent");
    rec.innerHTML = "";
    if (s.recentFiles && s.recentFiles.length) {
      const ph = document.createElement("option");
      ph.value = ""; ph.textContent = "Recent…"; ph.disabled = true; ph.selected = !s.currentFile;
      rec.appendChild(ph);
      s.recentFiles.forEach((f) => {
        const o = document.createElement("option"); o.value = f.path; o.textContent = f.name;
        if (f.path === s.currentFile) o.selected = true; rec.appendChild(o);
      });
      rec.style.display = "";
    } else rec.style.display = "none";
    setRunIco($("#drumsIco"), $("#drumsPlay"), s.isRunning, s.paused, $("#app"), "drums");
    $("#drumsStop").disabled = !s.isRunning;
    const sl = $("#drumsSlider"), inp = $("#drumsSpeedInput");
    sl.value = Math.min(300, Math.max(10, s.speed)); inp.value = s.speed;
    sl.style.setProperty("--fill", (((sl.value - sl.min) / (sl.max - sl.min)) * 100) + "%");
    $$("#drumsChips .chip").forEach((c) => c.classList.toggle("on", !!(s.options && s.options[c.dataset.opt])));
    if (!s.isRunning) { $("#drumsTot").textContent = s.totalText || "0:00:00"; $("#drumsCur").textContent = "0:00:00"; setBar("#drumsFill", "#drumsDot", 0); }
  }
  function updateDrumsTimeline(p) {
    const parts = (p.text || "").split(" / ");
    $("#drumsCur").textContent = parts[0] || ""; $("#drumsTot").textContent = parts[1] || "";
    setBar("#drumsFill", "#drumsDot", p.total ? p.current / p.total : 0);
  }

  // ---------- MIDI -> Teclas ----------
  let inputState = null;
  function applyInputState(s) {
    if (!s) return;
    inputState = s;
    const dev = $("#inputDevice");
    dev.innerHTML = "";
    if (s.devices && s.devices.length) {
      s.devices.forEach((d) => { const o = document.createElement("option"); o.value = d; o.textContent = d; if (d === s.device) o.selected = true; dev.appendChild(o); });
      dev.disabled = false;
    } else {
      const o = document.createElement("option"); o.textContent = "No device found"; dev.appendChild(o); dev.disabled = true;
    }
    const btn = $("#inputToggle"), st = $("#inputStatus");
    btn.classList.toggle("on", s.running);
    st.textContent = s.running ? "Live" : "Stopped";
    st.classList.toggle("live", s.running);
    $$("#inputChips .chip").forEach((c) => c.classList.toggle("on", !!(s.options && s.options[c.dataset.opt])));
  }

  // ---------- HOTKEYS ----------
  function applyHotkeys(hk) {
    if (!hk) return;
    $$(".hk-key").forEach((b) => {
      const v = hk[b.dataset.action];
      if (v) b.textContent = String(v).toUpperCase();
    });
  }
  let capturing = null;
  function startCapture(btn) {
    if (capturing) capturing.classList.remove("capturing");
    capturing = btn; btn.classList.add("capturing"); btn.textContent = "…";
  }
  function jsKeyToName(e) {
    const k = e.key;
    if (k === " ") return "space";
    if (/^F\d{1,2}$/.test(k)) return k.toLowerCase();
    if (k.length === 1) return k.toLowerCase();
    const map = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "enter", Escape: null, Tab: null };
    return map[k] !== undefined ? map[k] : null;
  }

  // shared helpers
  function setBar(fillSel, dotSel, ratio) {
    ratio = Math.max(0, Math.min(1, ratio));
    $(fillSel).style.width = (ratio * 100) + "%";
    $(dotSel).style.left = (ratio * 100) + "%";
  }
  function setRunIco(ico, btn, running, paused, appEl, kind) {
    const playing = running && !paused;
    if (kind === "drums") appEl.classList.toggle("drums-playing", playing);
    if (playing) {
      ico.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24"><rect x="6" y="5" width="4" height="14" rx="1.4" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1.4" fill="currentColor"/></svg>';
    } else {
      ico.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M8 5v14l11-7-11-7z" fill="currentColor"/></svg>';
    }
    btn.parentElement && btn.classList.toggle("is-playing", playing);
  }

  // ---------- PRACTICE / TREINO ----------
  const WHITE_PC = new Set([0, 2, 4, 5, 7, 9, 11]);
  let prSteps = [], prIdx = 0, prRemaining = [], prRunning = false, prLoaded = false;
  let prHits = 0, prWrong = 0, prCombo = 0, prMaxCombo = 0, prStartT = 0, prTotalNotes = 0;
  let prMinNote = 21, prMaxNote = 108, prWhiteW = 34, prDuration = 0;
  let prKeymap = {}, prMapChars = new Set();
  let freeMap = {};                 // "code|shift" -> note (for free play + audio feedback)
  const freeHeld = {};              // event.code -> note currently held (free play)
  let prMode = "step";              // "step" | "rhythm" | "free"
  let prRecords = {};               // { step:{...}, rhythm:{...} }
  const prNoteX = {}, prKeyEls = {};
  const hwBlocks = new Map();
  const PR_VIS = 14;

  // rhythm-mode engine state
  let ryRaf = 0, rySpeed = 1, ryPlayhead = 0, ryLast = 0, prSpeedSel = 1;
  let ryScore = 0, ryMult = 1, ryLife = 100, ryPerfect = 0, ryGood = 0, ryMiss = 0;
  const ryTiles = new Map();        // step index -> {el, cls}
  const ryJudged = new Map();       // step index -> "perfect"|"good"|"miss"
  const RY_LOOKAHEAD = 2.4;         // seconds a note is visible before its hit time
  const RY_PERFECT = 0.10, RY_GOOD = 0.26;   // timing windows (s) — forgiving
  const RY_TRAINER = { on: false, from: 0, to: 0 };  // section trainer
  // section-trainer adaptive speed ladder
  const RY_LADDER = [0.5, 0.65, 0.8, 1.0];
  let trLadderIx = 0;

  const isSharp = (n) => !WHITE_PC.has(((n % 12) + 12) % 12);
  const charForNote = (n) => prKeymap[n] != null ? prKeymap[n] : prKeymap[String(n)];

  // Map a mapping character to the PHYSICAL key + whether Shift is involved, so we
  // can match presses by physical key. This is what fixes chords that mix shifted
  // (sharps) and unshifted keys: holding Shift for one note no longer blocks the
  // others — the physical key counts regardless of Shift state.
  const SHIFT_DIGIT = { "!": "1", "@": "2", "#": "3", "$": "4", "%": "5", "^": "6", "&": "7", "*": "8", "(": "9", ")": "0" };
  function charToCode(ch) {
    if (/^[a-z]$/.test(ch)) return "Key" + ch.toUpperCase();
    if (/^[A-Z]$/.test(ch)) return "Key" + ch;
    if (/^[0-9]$/.test(ch)) return "Digit" + ch;
    if (SHIFT_DIGIT[ch]) return "Digit" + SHIFT_DIGIT[ch];
    return null;
  }
  const charNeedsShift = (ch) => /^[A-Z]$/.test(ch) || (ch in SHIFT_DIGIT);
  let prCodeSet = new Set();

  // Build the physical-key -> note map from the keys ACTUALLY on screen, so a
  // char that appears twice in the full mapping (e.g. "y" is both note 62 in the
  // 61-key range and note 97 in the 88-key extension) resolves to the key the
  // player can actually see and that will light up. Lowest on-screen note wins.
  function buildFreeMap() {
    freeMap = {};
    Object.keys(prKeyEls).map(Number).sort((a, b) => a - b).forEach((note) => {
      const ch = charForNote(note); if (ch == null) return;
      const code = charToCode(ch); if (!code) return;
      const key = code + "|" + (charNeedsShift(ch) ? "1" : "0");
      if (freeMap[key] === undefined) freeMap[key] = note;
    });
  }
  // Which note a physical key + Shift state should sound (prefers the exact
  // shift variant, then falls back so a plain key still plays its natural note).
  function noteForPress(code, shift) {
    let n = freeMap[code + "|" + (shift ? "1" : "0")];
    if (n === undefined) n = freeMap[code + "|0"];
    if (n === undefined) n = freeMap[code + "|1"];
    return n;
  }

  // practice piano sound
  const prActive = {};
  function ensurePracticeAudio() {
    ensureCtx(0.55);
    if (!audioCtx) return;
    loadPiano();
  }
  function prPlayNote(n) {
    if (!audioCtx) return;
    try { if (prActive[n]) prActive[n].stop(audioCtx.currentTime); } catch (_) {}
    try {
      prActive[n] = piano
        ? piano.play(n, audioCtx.currentTime, { gain: 0.9 })
        : playSynthPiano(n, 104);
    } catch (_) {}
  }

  function prEnter() {
    const sel = $("#prSong");
    sel.innerHTML = "";
    const files = (state && state.recentFiles) || [];
    const ph = document.createElement("option");
    ph.value = ""; ph.textContent = files.length ? "Choose a song…" : "No songs yet — open one";
    ph.disabled = true; ph.selected = !prLoaded && !prSteps.length; sel.appendChild(ph);
    const none = document.createElement("option");
    none.value = "__none__"; none.textContent = "— No song (free play) —";
    none.selected = prMode === "free" && !prSteps.length;
    sel.appendChild(none);
    files.forEach((f) => {
      const o = document.createElement("option");
      o.value = f.path; o.textContent = f.name;
      if (prLoaded && f.path === prCurrentPath) o.selected = true;
      sel.appendChild(o);
    });
    if (prLoaded && (prMode === "free" || prIdx < prSteps.length)) {
      prRunning = true;
      const a = api(); if (a && a.practiceActive) a.practiceActive(true);
    }
    if (prMode === "sheet") enterSheet();   // restore the Sheet panel on view re-entry
    renderRecords();
  }

  function renderRecords() {
    const host = $("#prRecords"); if (!host) return;
    const a = api(); if (!a || !a.practiceRecords) { host.innerHTML = ""; return; }
    a.practiceRecords().then((all) => {
      const rows = [];
      Object.keys(all || {}).forEach((song) => {
        const r = all[song];
        const best = r.rhythm || r.step || {};
        const badge = r.rhythm
          ? (r.rhythm.score || 0).toLocaleString() + " pts · " + (r.rhythm.accuracy || 0) + "%"
          : (best.accuracy || 0) + "% · combo " + (best.maxCombo || 0);
        rows.push('<div class="pr-rec-row"><span class="pr-rec-name">' + esc(cleanName(song)) +
          '</span><span class="pr-rec-badge">' + badge + '</span></div>');
      });
      host.innerHTML = rows.length
        ? '<div class="pr-rec-title">Your best runs</div>' + rows.slice(0, 6).join("")
        : "";
    }).catch(() => { host.innerHTML = ""; });
  }

  function stopPracticeNotes() {
    Object.keys(prActive).forEach((n) => {
      try { prActive[n].stop(); } catch (_) {}
      delete prActive[n];
    });
  }

  function prLeave() {
    stopPracticeNotes();
    stopRhythm();
    freePlayStop();
    sheetStop();
    clearFreeTrails();
    Object.keys(freeHeld).forEach((k) => delete freeHeld[k]);
    if (!prRunning) return;
    prRunning = false;
    const a = api(); if (a && a.practiceActive) a.practiceActive(false);
  }

  let prCurrentPath = "", prSongKey = "";
  function prLoad(res) {
    if (!res || !res.ok) {
      const msg = res && res.error === "empty"
        ? "This file has no notes Velo can map to keys."
        : "Couldn't load that MIDI file.";
      $("#prEmpty").hidden = false; $("#prGame").hidden = true;
      $("#prHud").hidden = true; $("#prFoot").hidden = true;
      $("#prEmpty").querySelector("p").textContent = msg;
      return;
    }
    prSteps = res.steps || [];
    prKeymap = res.keymap || {};
    prMapChars = new Set(Object.values(prKeymap));
    prCodeSet = new Set([...prMapChars].map(charToCode).filter(Boolean));
    prTotalNotes = prSteps.reduce((a, s) => a + s.notes.length, 0);
    prDuration = res.duration || 0;
    prMinNote = res.minNote; prMaxNote = res.maxNote;
    prCurrentPath = res.path || "";
    prSongKey = res.name || "";
    prRecords = res.records || {};
    RY_TRAINER.on = false; RY_TRAINER.from = 0; RY_TRAINER.to = prSteps.length - 1;
    prIdx = 0; prHits = 0; prWrong = 0; prCombo = 0; prMaxCombo = 0; prStartT = 0;
    prLoaded = true;
    renderTrainerRange();

    $("#prEmpty").hidden = true;
    $("#prResult").hidden = true; $("#prResult").innerHTML = "";
    $("#prConfetti").hidden = true; $("#prConfetti").innerHTML = "";
    $("#prGame").hidden = false; $("#prHud").hidden = false; $("#prFoot").hidden = false;
    $("#prTrainer").hidden = false;

    buildPiano();
    buildFreeMap();
    ensurePracticeAudio();
    const a = api(); if (a && a.practiceActive) a.practiceActive(true);
    prStartMode();
  }

  // Start (or restart) whichever practice mode is selected.
  function prStartMode() {
    stopRhythm(); freePlayStop(); clearFreeTrails();
    // make sure the right panels are visible (we may be coming from Free play)
    $("#prGame").hidden = false; $("#prEmpty").hidden = true;
    $("#prHud").hidden = false; $("#prFoot").hidden = false; $("#prTrainer").hidden = false;
    $("#prRestart").hidden = false; updateFreePlayBtn();
    hwBlocks.clear(); $("#prTrack").innerHTML = "";
    Object.values(prKeyEls).forEach((el) => el.classList.remove("want", "hit"));
    $("#prResult").hidden = true;
    prHits = 0; prWrong = 0; prCombo = 0; prMaxCombo = 0; prStartT = 0;
    $("#prHud").classList.toggle("rhythm", prMode === "rhythm");
    setHudMode(); setHint();
    if (prMode === "rhythm") {
      startRhythm();
    } else {
      prIdx = RY_TRAINER.on ? RY_TRAINER.from : 0;
      prRunning = true;
      armChord();
      updateHud();
    }
  }

  function buildPiano() {
    const game = $("#prGame");
    const avail = Math.max(360, (game.clientWidth || 800) - 4);
    // snap the endpoints to white keys so the keyboard ends cleanly. No ±1
    // padding: that used to pull in a neighbouring note from the 88-key
    // extension (e.g. note 35 "t", note 97 "y") and create duplicate labels.
    let lo = Math.max(0, prMinNote), hi = Math.min(127, prMaxNote);
    while (isSharp(lo) && lo > 0) lo--;
    while (isSharp(hi) && hi < 127) hi++;
    prMinNote = lo; prMaxNote = hi;

    let whiteCount = 0;
    for (let n = lo; n <= hi; n++) if (!isSharp(n)) whiteCount++;
    prWhiteW = Math.max(15, Math.min(52, Math.floor(avail / Math.max(1, whiteCount))));
    const pianoWidth = whiteCount * prWhiteW;
    const off = Math.max(0, (avail - pianoWidth) / 2);
    const fullW = Math.max(pianoWidth, avail);
    const blackW = Math.round(prWhiteW * 0.62);
    const ph = Math.round(Math.min(168, Math.max(120, prWhiteW * 3.4)));

    const stage = $("#prStage");
    stage.style.width = fullW + "px";
    stage.style.setProperty("--ph", ph + "px");
    stage.style.setProperty("--slot", "46px");

    const piano = $("#prPiano");
    piano.innerHTML = "";
    for (const k in prNoteX) delete prNoteX[k];
    for (const k in prKeyEls) delete prKeyEls[k];

    let wi = 0;
    for (let n = lo; n <= hi; n++) {
      const white = !isSharp(n);
      const el = document.createElement("div");
      let x;
      if (white) {
        const left = off + wi * prWhiteW;
        el.className = "pk pk-white";
        el.style.left = left + "px"; el.style.width = prWhiteW + "px";
        x = left + prWhiteW / 2; wi++;
      } else {
        const center = off + wi * prWhiteW;
        el.className = "pk pk-black";
        el.style.left = (center - blackW / 2) + "px"; el.style.width = blackW + "px";
        x = center;
      }
      prNoteX[n] = x;
      el.dataset.note = n;
      const ch = charForNote(n);
      if (ch != null) {
        const lbl = document.createElement("span");
        lbl.className = "pk-lbl"; lbl.textContent = ch;
        el.appendChild(lbl);
      }
      prKeyEls[n] = el;
      piano.appendChild(el);
    }

    // faint lane lines at white-key boundaries
    const lanes = $("#prLanes");
    lanes.innerHTML = "";
    for (let i = 0; i <= whiteCount; i++) {
      const ln = document.createElement("div");
      ln.className = "hw-lane";
      ln.style.left = (off + i * prWhiteW) + "px";
      lanes.appendChild(ln);
    }
  }

  function makeBlock(p) {
    const step = prSteps[p];
    if (!step) return;
    const b = document.createElement("div");
    b.className = "hw-chord";
    b.style.setProperty("--p", p);
    step.notes.forEach((note) => {
      const s = document.createElement("span");
      s.className = "hw-note" + (isSharp(note.note) ? " sharp" : "");
      s.style.setProperty("--x", prNoteX[note.note] || 0);
      s.textContent = note.char;
      s.dataset.note = note.note;
      b.appendChild(s);
    });
    $("#prTrack").appendChild(b);
    hwBlocks.set(p, b);
  }

  function renderWindow() {
    const lo = prIdx - 1, hi = prIdx + PR_VIS;
    hwBlocks.forEach((el, p) => {
      if (p < lo || p > hi) { el.remove(); hwBlocks.delete(p); }
    });
    for (let p = Math.max(0, prIdx); p <= hi; p++) {
      if (p < prSteps.length && !hwBlocks.has(p)) makeBlock(p);
    }
    hwBlocks.forEach((el, p) => el.classList.toggle("current", p === prIdx));
    $("#prTrack").style.setProperty("--idx", prIdx);
  }

  function armChord() {
    Object.values(prKeyEls).forEach((el) => el.classList.remove("want", "hit"));
    const step = prSteps[prIdx] || { notes: [] };
    prRemaining = step.notes.map((n) => ({ note: n.note, char: n.char }));
    prRemaining.forEach((n) => { const el = prKeyEls[n.note]; if (el) el.classList.add("want"); });
    renderWindow();
    autoscroll();
  }

  function autoscroll() {
    const step = prSteps[prIdx];
    if (!step || !step.notes.length) return;
    const xs = step.notes.map((n) => prNoteX[n.note] || 0);
    const avg = xs.reduce((a, b) => a + b, 0) / xs.length;
    const sc = $("#prScroll");
    sc.scrollTo({ left: Math.max(0, avg - sc.clientWidth / 2), behavior: "smooth" });
  }

  function rebuildPracticeLayout() {
    if (prMode === "sheet") return;   // letter flow re-wraps via CSS; nothing to rebuild
    buildPiano();
    if (prMode === "rhythm") {
      ryTiles.forEach((o) => o.el.remove()); ryTiles.clear(); $("#prTrack").innerHTML = "";
    } else {
      prRemaining.forEach((n) => { const el = prKeyEls[n.note]; if (el) el.classList.add("want"); });
      hwBlocks.forEach((el) => el.querySelectorAll(".hw-note").forEach((s) =>
        s.style.setProperty("--x", prNoteX[s.dataset.note] || 0)));
      autoscroll();
    }
  }

  function advance() {
    const oldP = prIdx;
    const done = hwBlocks.get(oldP);
    if (done) {
      done.classList.add("cleared");
      setTimeout(() => { done.remove(); hwBlocks.delete(oldP); }, 320);
    }
    prIdx++;
    if (prIdx > trainerTo() || prIdx >= prSteps.length) { updateHud(); setTimeout(finishPractice, 280); return; }
    armChord();
    updateHud();
  }

  function bumpCombo() {
    const c = $("#prCombo");
    c.classList.toggle("zero", prCombo === 0);
    $("#prComboN").textContent = prCombo;
    c.classList.remove("bump"); void c.offsetWidth;
    if (prCombo > 0) c.classList.add("bump");
  }

  function flashWrong(ch) {
    const g = $("#prGame");
    g.classList.add("shake", "bad");
    setTimeout(() => g.classList.remove("shake", "bad"), 330);
    for (const n in prKeyEls) {
      const el = prKeyEls[n];
      if (charForNote(n) === ch && !el.classList.contains("want")) {
        el.classList.add("bad");
        setTimeout(() => el.classList.remove("bad"), 330);
      }
    }
  }

  // ===== RHYTHM MODE (timed) =====================================
  const trainerFrom = () => RY_TRAINER.on ? RY_TRAINER.from : 0;
  const trainerTo = () => RY_TRAINER.on ? RY_TRAINER.to : prSteps.length - 1;

  function startRhythm() {
    stopRhythm();
    ryScore = 0; ryMult = 1; ryLife = 100; ryPerfect = 0; ryGood = 0; ryMiss = 0;
    prCombo = 0; prMaxCombo = 0; ryLast = 0;
    ryJudged.clear(); ryTiles.clear(); $("#prTrack").innerHTML = "";
    rySpeed = RY_TRAINER.on ? RY_LADDER[trLadderIx] : prSpeedSel;
    const firstT = (prSteps[trainerFrom()] || { t: 0 }).t;
    ryPlayhead = firstT - RY_LOOKAHEAD - 3.0;   // 3s count-in before notes enter
    prRunning = true; prStartT = Date.now();
    setHudMode();
    updateRhythmHud();
    ryRaf = requestAnimationFrame(ryFrame);
  }

  function stopRhythm() {
    if (ryRaf) cancelAnimationFrame(ryRaf);
    ryRaf = 0;
    const c = $("#prCountIn"); if (c) c.hidden = true;
  }

  function highwayPps() {
    const h = $("#prTrack").clientHeight || 320;
    return h / RY_LOOKAHEAD;
  }

  function makeRyTile(i) {
    const step = prSteps[i]; if (!step) return null;
    const b = document.createElement("div");
    b.className = "ry-tile";
    step.notes.forEach((note) => {
      const s = document.createElement("span");
      s.className = "hw-note" + (isSharp(note.note) ? " sharp" : "");
      s.style.setProperty("--x", prNoteX[note.note] || 0);
      s.textContent = note.char; s.dataset.note = note.note;
      b.appendChild(s);
    });
    $("#prTrack").appendChild(b);
    return b;
  }

  function ryFrame(ts) {
    const nowS = ts / 1000;
    const dt = ryLast ? Math.min(0.05, nowS - ryLast) : 0;
    ryLast = nowS;
    ryPlayhead += dt * rySpeed;

    const firstEnter = (prSteps[trainerFrom()] || { t: 0 }).t - RY_LOOKAHEAD;
    const cin = $("#prCountIn");
    if (ryPlayhead < firstEnter) {
      cin.hidden = false; cin.textContent = String(Math.ceil(firstEnter - ryPlayhead));
    } else if (!cin.hidden && cin.textContent !== "GO") {
      cin.textContent = "GO";
      setTimeout(() => { cin.hidden = true; }, 300);
    }

    renderRhythmTiles();
    judgePassed();

    const endT = (prSteps[trainerTo()] || { t: 0 }).t + 0.6;
    if (ryPlayhead > endT) { finishRhythm(false); return; }
    ryRaf = requestAnimationFrame(ryFrame);
  }

  function renderRhythmTiles() {
    const pps = highwayPps();
    const lo = ryPlayhead - 0.4, hi = ryPlayhead + RY_LOOKAHEAD + 0.1;
    ryTiles.forEach((o, i) => {
      const t = prSteps[i].t;
      if (t < lo || t > hi) { o.el.remove(); ryTiles.delete(i); }
    });
    for (let i = trainerFrom(); i <= trainerTo(); i++) {
      const st = prSteps[i]; if (!st || st.t < lo || st.t > hi) continue;
      let o = ryTiles.get(i);
      if (!o) { const el = makeRyTile(i); if (!el) continue; o = { el }; ryTiles.set(i, o); }
      o.el.style.bottom = ((st.t - ryPlayhead) * pps) + "px";
      const v = ryJudged.get(i);
      if (v && !o.cls) { o.el.classList.add(v === "miss" ? "ry-miss" : "ry-hit"); o.cls = true; }
    }
  }

  function judgePassed() {
    for (let i = trainerFrom(); i <= trainerTo(); i++) {
      if (ryJudged.has(i)) continue;
      if (prSteps[i].t < ryPlayhead - RY_GOOD) ryMissStep(i);
      else break;  // steps are time-ordered: first future one ends the scan
    }
  }

  function ryJudgeHit(i, dt) {
    const verdict = Math.abs(dt) <= RY_PERFECT ? "perfect" : "good";
    ryJudged.set(i, verdict);
    if (verdict === "perfect") ryPerfect++; else ryGood++;
    prCombo++; if (prCombo > prMaxCombo) prMaxCombo = prCombo;
    ryMult = Math.min(8, 1 + Math.floor(prCombo / 10));
    ryScore += (verdict === "perfect" ? 100 : 50) * ryMult;
    ryLife = Math.min(100, ryLife + (verdict === "perfect" ? 1.6 : 0.8));
    prSteps[i].notes.forEach((n) => {
      const el = prKeyEls[n.note];
      if (el) { el.classList.add("hit"); setTimeout(() => el.classList.remove("hit"), 150); }
    });
    floatJudge(verdict);
    bumpCombo(); updateRhythmHud();
  }

  function ryMissStep(i) {
    ryJudged.set(i, "miss"); ryMiss++; prCombo = 0; ryMult = 1;
    ryLife -= 5; floatJudge("miss"); bumpCombo(); updateRhythmHud();
    if (ryLife <= 0) finishRhythm(true);
  }

  function ryWrong() {
    prCombo = 0; ryMult = 1; ryLife -= 2;
    const g = $("#prGame"); g.classList.add("bad"); setTimeout(() => g.classList.remove("bad"), 180);
    floatJudge("x"); bumpCombo(); updateRhythmHud();
    if (ryLife <= 0) finishRhythm(true);
  }

  function onRhythmKey(e) {
    const code = e.code;
    if (!code || !prCodeSet.has(code)) return;  // non-piano keys ignored
    e.preventDefault();
    // always sound the pressed note so it feels responsive even if the timing
    // judgment is a miss — fixes "I pressed it and nothing played"
    const sounded = noteForPress(code, e.shiftKey);
    if (sounded !== undefined) prPlayNote(sounded);
    let best = -1, bestdt = 999;
    for (let i = trainerFrom(); i <= trainerTo(); i++) {
      if (ryJudged.has(i)) continue;
      const d = prSteps[i].t - ryPlayhead;
      if (d > RY_GOOD) break;            // too early / future — stop (ordered)
      if (d < -RY_GOOD) continue;        // already past its window
      if (prSteps[i].notes.some((n) => charToCode(n.char) === code)) {
        if (Math.abs(d) < Math.abs(bestdt)) { best = i; bestdt = d; }
      }
    }
    if (best >= 0) ryJudgeHit(best, bestdt);
    else ryWrong();
  }

  let floatTimer = 0;
  function floatJudge(kind) {
    const host = $("#prJudge"); if (!host) return;
    const txt = kind === "perfect" ? "PERFECT" : kind === "good" ? "GOOD" : kind === "miss" ? "MISS" : "✕";
    host.className = "pr-judge j-" + kind;
    host.textContent = txt;
    host.hidden = false;
    host.classList.remove("pop"); void host.offsetWidth; host.classList.add("pop");
    clearTimeout(floatTimer);
    floatTimer = setTimeout(() => { host.hidden = true; }, 520);
  }

  function setHudMode() {
    const rhythm = prMode === "rhythm";
    $("#prStatProgL").textContent = rhythm ? "score" : "notes";
    $("#prStatAccL").textContent = rhythm ? "mult" : "accuracy";
    $("#prBar").classList.toggle("life", rhythm);
  }

  function updateRhythmHud() {
    $("#prProg").textContent = ryScore.toLocaleString();
    $("#prAcc").textContent = "x" + ryMult;
    const bar = $("#prBar");
    bar.style.width = Math.max(0, ryLife) + "%";
    bar.classList.toggle("low", ryLife <= 30);
  }

  // ===== SECTION TRAINER =========================================
  function renderTrainerRange() {
    const a = $("#trFrom"), b = $("#trTo");
    if (!a || !b) return;
    const max = Math.max(1, prSteps.length - 1);
    a.max = max; b.max = max;
    if (!RY_TRAINER.on) { RY_TRAINER.from = 0; RY_TRAINER.to = max; }
    a.value = RY_TRAINER.from; b.value = RY_TRAINER.to;
    const wrap = $("#prTrainer"); if (wrap) wrap.classList.toggle("on", RY_TRAINER.on);
    const tg = $("#trToggle"); if (tg) tg.classList.toggle("on", RY_TRAINER.on);
    const lbl = $("#trLabel");
    if (lbl) {
      lbl.textContent = RY_TRAINER.on
        ? `Looping ${RY_TRAINER.from + 1}–${RY_TRAINER.to + 1} · ${Math.round(RY_LADDER[trLadderIx] * 100)}% speed`
        : "whole song";
    }
    // paint the selected range between the two handles
    const fill = $("#trFill");
    if (fill) {
      const lo = (RY_TRAINER.from / max) * 100, hi = (RY_TRAINER.to / max) * 100;
      fill.style.left = lo + "%";
      fill.style.width = Math.max(0, hi - lo) + "%";
    }
  }

  // ===== FREE PLAY (sandbox piano) ===============================
  function setHint() {
    const el = $("#prHint"); if (!el) return;
    el.innerHTML = prMode === "free"
      ? "Free play — type or click the keys (sharps need <b>Shift</b>). Pick a song and hit <b>Play (preview)</b> to watch it here. Your Player <b>play hotkey</b> also works here — it autoplays the Player's selected song for real (and into games)."
      : prMode === "rhythm"
        ? "Hit each note as it reaches the line — <b>Perfect</b>/<b>Good</b>/<b>Miss</b>. Sharps need <b>Shift</b>."
        : "Press the highlighted keys. Sharps (lit black keys) need <b>Shift</b>. A wrong key won't pass until you hit the right one.";
  }

  function enterFree() {
    const go = () => {
      prMode = "free";
      prMinNote = 36; prMaxNote = 96;   // the classic 61-key virtual-piano layout
      stopRhythm(); freePlayStop();
      $("#prEmpty").hidden = true; $("#prResult").hidden = true;
      $("#prConfetti").hidden = true; $("#prConfetti").innerHTML = "";
      $("#prGame").hidden = false; $("#prHud").hidden = true;
      $("#prTrainer").hidden = true; $("#prFoot").hidden = false;
      setHint();
      buildPiano();
      hwBlocks.clear(); $("#prTrack").innerHTML = "";
      ryTiles.forEach((o) => o.el.remove()); ryTiles.clear();
      buildFreeMap();
      ensurePracticeAudio();
      prLoaded = true; prRunning = true;
      $("#prScroll").scrollLeft = 0;
      $("#prRestart").hidden = true;
      updateFreePlayBtn();
      const a = api(); if (a && a.practiceActive) a.practiceActive(true);
    };
    if (prKeymap && Object.keys(prKeymap).length) go();
    else {
      const a = api();
      if (a && a.practiceKeymap) a.practiceKeymap().then((m) => { prKeymap = m || {}; go(); });
      else go();
    }
  }

  function onFreeKey(e) {
    if (e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    const code = e.code; if (!code) return;
    const n = noteForPress(code, e.shiftKey);
    if (n === undefined || freeHeld[code] !== undefined) return;
    e.preventDefault();
    prPlayNote(n); freeHeld[code] = n;
    const k = prKeyEls[n]; if (k) k.classList.add("hit");   // lit only while held
    startTrail(code, n);
  }

  function onFreeKeyUp(e) {
    const n = freeHeld[e.code];
    if (n === undefined) return;
    delete freeHeld[e.code];
    if (!noteHeld(n)) { const k = prKeyEls[n]; if (k) k.classList.remove("hit"); }
    releaseTrail(e.code);
  }

  // --- rising trails: a ribbon grows up from the key while held, then floats
  //     up and fades on release (like onlinepianist / a MIDI visualizer). ---
  const freeTrails = new Map();   // unique trailId -> {el, note, t0, held, relAt, len}
  const freeKeyTrail = {};        // source id (key code / "mouse") -> active trailId
  let freeRaf = 0, trailSeq = 0;
  const TRAIL_PPS = 230;          // pixels/second the ribbon grows & rises

  function noteHeld(note) {            // is this note still physically held down?
    for (const k in freeHeld) if (freeHeld[k] === note) return true;
    return false;
  }

  // Each press spawns its OWN trail (so tapping a key twice makes two ribbons);
  // srcId just lets the matching key-up release the right one.
  function createTrailEl(note) {
    const track = $("#prTrack"); if (!track) return null;
    const sharp = isSharp(note);
    const el = document.createElement("div");
    el.className = "free-trail" + (sharp ? " sharp" : "");
    el.style.left = prNoteX[note] + "px";
    el.style.width = Math.round((sharp ? prWhiteW * 0.62 : prWhiteW) * 0.74) + "px";
    el.style.bottom = "0px";
    track.appendChild(el);
    return el;
  }

  function startTrail(srcId, note) {
    if (prMode !== "free" || prNoteX[note] == null) return;
    const el = createTrailEl(note); if (!el) return;
    el.style.height = "0px";
    const tid = ++trailSeq;
    freeTrails.set(tid, { el, note, t0: performance.now(), held: true, relAt: 0, len: 0 });
    freeKeyTrail[srcId] = tid;
    if (!freeRaf) freeRaf = requestAnimationFrame(trailAnim);
  }

  // A self-contained ribbon already in the "released" state with a fixed length
  // — used for keys the cursor sweeps past during a fast glissando, so each one
  // still shows a visible trail instead of a near-zero blip.
  function spawnReleasedTrail(note, len) {
    if (prMode !== "free" || prNoteX[note] == null) return;
    const el = createTrailEl(note); if (!el) return;
    el.style.height = len + "px";
    const now = performance.now();
    freeTrails.set(++trailSeq, { el, note, t0: now, held: false, relAt: now, len });
    if (!freeRaf) freeRaf = requestAnimationFrame(trailAnim);
  }

  function releaseTrail(srcId) {
    const tid = freeKeyTrail[srcId];
    if (tid == null) return;
    delete freeKeyTrail[srcId];
    const tr = freeTrails.get(tid);
    if (tr && tr.held) { tr.held = false; tr.relAt = performance.now(); }
  }

  function dropTrail(id, tr) {
    tr.el.remove();
    freeTrails.delete(id);
    // safety net: if a key-up was ever missed, unlight the key once its trail ends
    if (!noteHeld(tr.note)) { const k = prKeyEls[tr.note]; if (k) k.classList.remove("hit"); }
  }

  function clearFreeTrails() {
    freeTrails.forEach((tr) => { tr.el.remove(); const k = prKeyEls[tr.note]; if (k) k.classList.remove("hit"); });
    freeTrails.clear();
    Object.keys(freeKeyTrail).forEach((k) => delete freeKeyTrail[k]);
    if (freeRaf) { cancelAnimationFrame(freeRaf); freeRaf = 0; }
  }

  function trailAnim(ts) {
    const track = $("#prTrack");
    const H = (track && track.clientHeight) || 320;
    let any = false;
    freeTrails.forEach((tr, id) => {
      // safety: nothing stays held forever (e.g. a missed key-up from autoplay)
      if (tr.held && (ts - tr.t0) / 1000 > 6) { tr.held = false; tr.relAt = ts; }
      if (tr.held) {
        tr.len = Math.min(H, (ts - tr.t0) / 1000 * TRAIL_PPS);
        tr.el.style.height = tr.len + "px";
        tr.el.style.bottom = "0px";
        any = true;
      } else {
        const dt = (ts - tr.relAt) / 1000;
        tr.el.style.height = tr.len + "px";
        tr.el.style.bottom = (dt * TRAIL_PPS) + "px";
        tr.el.style.opacity = Math.max(0, 1 - dt / 1.1).toFixed(3);
        if (dt > 1.15) dropTrail(id, tr);
        else any = true;
      }
    });
    freeRaf = any ? requestAnimationFrame(trailAnim) : 0;
  }

  // --- Free-play auto-player: plays the selected song on the free piano
  //     (lights keys + piano sound, timed) so you can watch it play itself. ---
  let fpRaf = 0, fpPlaying = false, fpPlayhead = 0, fpLast = 0, fpIdx = 0;
  const fpTiles = new Map();
  const FP_LOOKAHEAD = 2.4;

  function renderFreeTiles() {
    const track = $("#prTrack");
    const pps = (track.clientHeight || 320) / FP_LOOKAHEAD;
    const lo = fpPlayhead - 0.4, hi = fpPlayhead + FP_LOOKAHEAD + 0.1;
    fpTiles.forEach((el, i) => {
      const t = prSteps[i] && prSteps[i].t;
      if (t == null || t < lo || t > hi) { el.remove(); fpTiles.delete(i); }
    });
    for (let i = 0; i < prSteps.length; i++) {
      const st = prSteps[i]; if (st.t < lo) continue; if (st.t > hi) break;
      let el = fpTiles.get(i);
      if (!el) {
        el = document.createElement("div"); el.className = "ry-tile";
        st.notes.forEach((n) => {
          if (prNoteX[n.note] == null) return;   // note off the 61-key board
          const s = document.createElement("span");
          s.className = "hw-note" + (isSharp(n.note) ? " sharp" : "");
          s.style.setProperty("--x", prNoteX[n.note]); s.textContent = n.char;
          el.appendChild(s);
        });
        track.appendChild(el); fpTiles.set(i, el);
      }
      el.style.bottom = ((st.t - fpPlayhead) * pps) + "px";
      if (st.t <= fpPlayhead && !el.dataset.lit) { el.classList.add("ry-hit"); el.dataset.lit = "1"; }
    }
  }

  const PLAY_ICO = '<svg viewBox="0 0 24 24" width="15" height="15"><path d="M8 5v14l11-7-11-7z" fill="currentColor"/></svg>';
  const STOP_ICO = '<svg viewBox="0 0 24 24" width="15" height="15"><rect x="6" y="5" width="12" height="12" rx="2" fill="currentColor"/></svg>';
  function updateFreePlayBtn() {
    const b = $("#prFreePlay"); if (!b) return;
    b.hidden = !(prMode === "free" && prSteps.length > 0);
    b.innerHTML = (fpPlaying ? STOP_ICO + " Stop" : PLAY_ICO + " Play (preview)");
  }

  function freePlayStop() {
    fpPlaying = false;
    if (fpRaf) cancelAnimationFrame(fpRaf); fpRaf = 0;
    fpTiles.forEach((el) => el.remove()); fpTiles.clear();
    if ($("#prTrack")) $("#prTrack").innerHTML = "";
    Object.values(prKeyEls).forEach((el) => el.classList.remove("hit"));
    stopPracticeNotes();
    updateFreePlayBtn();
  }

  function freePlayStart() {
    if (prMode !== "free" || !prSteps.length) return;
    freePlayStop();
    ensurePracticeAudio();
    fpIdx = 0; fpLast = 0; fpPlayhead = (prSteps[0].t || 0) - FP_LOOKAHEAD - 0.6; fpPlaying = true;
    updateFreePlayBtn();
    fpRaf = requestAnimationFrame(fpFrame);
  }

  function fpFrame(ts) {
    const now = ts / 1000;
    const dt = fpLast ? Math.min(0.05, now - fpLast) : 0;
    fpLast = now;
    fpPlayhead += dt;
    while (fpIdx < prSteps.length && prSteps[fpIdx].t <= fpPlayhead) {
      const notes = prSteps[fpIdx].notes;
      notes.forEach((n) => {
        prPlayNote(n.note);
        const el = prKeyEls[n.note];
        if (el) el.classList.add("hit");
      });
      const snapshot = notes.slice();
      setTimeout(() => {
        snapshot.forEach((n) => { const el = prKeyEls[n.note]; if (el) el.classList.remove("hit"); });
      }, 220);
      fpIdx++;
    }
    renderFreeTiles();
    if (fpIdx >= prSteps.length && fpPlayhead > (prSteps[prSteps.length - 1].t + 0.6)) { freePlayStop(); return; }
    fpRaf = requestAnimationFrame(fpFrame);
  }

  function freePlayToggle() { if (fpPlaying) freePlayStop(); else freePlayStart(); }

  // Loads a song for Free-play auto-play WITHOUT switching to step/rhythm — keeps
  // the 61-key piano and just enables the Play button.
  function freeLoadSong(res) {
    prSteps = res.steps || [];
    prSongKey = res.name || "";
    prDuration = res.duration || 0;
    if (res.keymap) prKeymap = res.keymap;
    freePlayStop();
    updateFreePlayBtn();
  }

  // Clear the selected song — back to a clean piano with no auto-play.
  function freeClearSong() {
    freePlayStop();
    prSteps = []; prSongKey = "";
    updateFreePlayBtn();
  }

  // Route a freshly loaded song to the right setup based on the active mode.
  function applyLoaded(res) {
    if (!res || !res.ok) return;
    if (prMode === "free") freeLoadSong(res);
    else if (prMode === "sheet") sheetLoadSong(res);
    else prLoad(res);
  }

  function onPracticeKey(e) {
    if (!prRunning || e.repeat || e.ctrlKey || e.metaKey || e.altKey) return;
    if (prMode === "sheet") { onSheetKey(e); return; }   // play-along: type the lit keys
    if (prMode === "free") { onFreeKey(e); return; }
    if (prMode === "rhythm") { onRhythmKey(e); return; }
    const code = e.code;
    if (!code) return;

    // remaining notes whose physical key matches the one just pressed
    const cands = [];
    prRemaining.forEach((n, i) => { if (charToCode(n.char) === code) cands.push({ n, i }); });

    if (cands.length === 0) {
      if (prCodeSet.has(code)) {
        e.preventDefault();
        // sound the note you actually pressed, even though it's wrong, so the
        // keyboard feels responsive (matches Rhythm mode) — "I hear what I hit"
        const sounded = noteForPress(code, e.shiftKey);
        if (sounded !== undefined) prPlayNote(sounded);
        registerWrong(e.key);
      }
      return;  // not a piano key (Shift, space, etc.) — ignore, no penalty
    }
    e.preventDefault();

    // if a natural + its sharp share this physical key in the same chord, the
    // Shift state decides which one; otherwise any Shift state is accepted
    let pick = cands[0];
    if (cands.length > 1) {
      pick = cands.find((o) => charNeedsShift(o.n.char) === e.shiftKey) || cands[0];
    }
    const noteObj = pick.n;
    prRemaining.splice(prRemaining.indexOf(noteObj), 1);
    prHits++; prCombo++; if (prCombo > prMaxCombo) prMaxCombo = prCombo;
    if (!prStartT) prStartT = Date.now();
    prPlayNote(noteObj.note);
    const kel = prKeyEls[noteObj.note];
    if (kel) { kel.classList.remove("want"); kel.classList.add("hit"); }
    const blk = hwBlocks.get(prIdx);
    if (blk) {
      const pill = blk.querySelector('.hw-note[data-note="' + noteObj.note + '"]');
      if (pill) { pill.classList.remove("sharp"); pill.classList.add("done"); }
    }
    bumpCombo();
    if (prRemaining.length === 0) advance();
    else updateHud();
  }

  function registerWrong(ch) {
    prWrong++; prCombo = 0;
    flashWrong(ch);
    bumpCombo();
    updateHud();
  }

  function updateHud() {
    $("#prProg").textContent = prHits + " / " + prTotalNotes;
    const tot = prHits + prWrong;
    $("#prAcc").textContent = (tot ? Math.round((prHits / tot) * 100) : 100) + "%";
    $("#prBar").style.width = (prSteps.length ? (prIdx / prSteps.length) * 100 : 0) + "%";
  }

  const fmtTime = (secs) => Math.floor(secs / 60) + ":" + String(secs % 60).padStart(2, "0");
  const rstat = (v, l) => '<div class="pr-rstat"><b>' + v + '</b><span>' + l + '</span></div>';

  function showResultCard(opts) {
    const res = $("#prResult");
    res.innerHTML =
      '<span class="pr-rmark"><svg viewBox="0 0 24 24" width="42" height="42" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 13 4 4L19 7"/></svg></span>' +
      (opts.stars ? '<div class="pr-stars">' + opts.stars + '</div>' : '') +
      '<h2>' + opts.headline + '</h2>' +
      (opts.isPB ? '<div class="pr-pb">★ New personal best!</div>' : '') +
      (opts.extra ? '<div class="pr-extra">' + opts.extra + '</div>' : '') +
      '<div class="pr-rstats">' + opts.statsHtml + '</div>' +
      '<div class="pr-ractions">' +
      '<button class="btn primary" id="prAgain">Practice again</button>' +
      '<button class="btn ghost" id="prAnother">Another song</button>' +
      '</div>';
    res.hidden = false;
    $("#prAgain").addEventListener("click", restartPractice);
    $("#prAnother").addEventListener("click", () => call("getState").then(() => { prLoaded = false; showPracticeEmpty(); }));
  }

  function finalizeResult(mode, score, acc, maxCombo, secs, headline, stars, statsHtml, extra) {
    const render = (isPB) => showResultCard({ headline, stars, statsHtml, isPB, extra });
    const a = api();
    if (a && a.practiceSaveResult && prSongKey) {
      a.practiceSaveResult(prSongKey, mode, score, acc, maxCombo, secs)
        .then((r) => render(r && r.isPB)).catch(() => render(false));
    } else render(false);
  }

  function finishPractice() {
    prRunning = false; stopRhythm();
    const a = api(); if (a && a.practiceActive) a.practiceActive(false);
    const tot = prHits + prWrong;
    const acc = tot ? Math.round((prHits / tot) * 100) : 100;
    const secs = prStartT ? Math.round((Date.now() - prStartT) / 1000) : 0;
    const stars = acc >= 98 ? "★★★" : acc >= 90 ? "★★☆" : acc >= 75 ? "★☆☆" : "☆☆☆";
    const headline = acc >= 98 ? "Flawless!" : acc >= 90 ? "Nailed it!" : acc >= 70 ? "Nice run!" : "Completed";
    const stats = rstat(acc + "%", "accuracy") + rstat(prMaxCombo, "max combo") + rstat(fmtTime(secs), "time");
    finalizeResult("step", 0, acc, prMaxCombo, secs, headline, stars, stats);
    confetti();
  }

  function finishRhythm(failed) {
    stopRhythm(); prRunning = false;
    const a = api(); if (a && a.practiceActive) a.practiceActive(false);
    const judged = ryPerfect + ryGood + ryMiss;
    const acc = judged ? Math.round(((ryPerfect + ryGood) / judged) * 100) : 0;
    const secs = prStartT ? Math.round((Date.now() - prStartT) / 1000) : 0;
    let extra = "";
    if (RY_TRAINER.on && !failed && acc >= 85 && trLadderIx < RY_LADDER.length - 1) {
      trLadderIx++; extra = "Section cleared — speeding up to " + Math.round(RY_LADDER[trLadderIx] * 100) + "%";
      renderTrainerRange();
    }
    const headline = failed ? "Out of life" : (acc >= 95 ? "Incredible!" : acc >= 80 ? "Great run!" : "Run complete");
    const stars = acc >= 95 ? "★★★" : acc >= 80 ? "★★☆" : acc >= 60 ? "★☆☆" : "☆☆☆";
    const stats = rstat(ryScore.toLocaleString(), "score") + rstat(acc + "%", "accuracy") +
      rstat(prMaxCombo, "max combo") + rstat(ryPerfect, "perfect") + rstat(ryMiss, "miss");
    finalizeResult("rhythm", ryScore, acc, prMaxCombo, secs, headline, stars, stats, extra);
    if (!failed) confetti();
  }

  function showPracticeEmpty() {
    $("#prGame").hidden = true; $("#prHud").hidden = true; $("#prFoot").hidden = true;
    $("#prTrainer").hidden = true;
    $("#prSheet").hidden = true; sheetStop();
    $("#prEmpty").hidden = false;
    prEnter();
  }

  function restartPractice() {
    $("#prResult").hidden = true; $("#prResult").innerHTML = "";
    $("#prConfetti").hidden = true; $("#prConfetti").innerHTML = "";
    ensurePracticeAudio();
    const a = api(); if (a && a.practiceActive) a.practiceActive(true);
    bumpCombo();
    prStartMode();
  }

  function confetti() {
    const box = $("#prConfetti");
    box.innerHTML = ""; box.hidden = false;
    const colors = ["#c8ff4d", "#9fd62f", "#ffffff", "#7ee0ff"];
    for (let i = 0; i < 90; i++) {
      const c = document.createElement("i");
      c.className = "pr-conf";
      c.style.left = Math.random() * 100 + "%";
      c.style.background = colors[(Math.random() * colors.length) | 0];
      c.style.animationDuration = (1.6 + Math.random() * 1.8) + "s";
      c.style.animationDelay = (Math.random() * 0.5) + "s";
      c.style.transform = "rotate(" + (Math.random() * 360) + "deg)";
      box.appendChild(c);
    }
    setTimeout(() => { box.hidden = true; box.innerHTML = ""; }, 4000);
  }

  function practiceChooseFile() {
    const a = api(); if (!a || !a.practiceChoose) return;
    a.practiceChoose().then((res) => { if (res && res.ok) applyLoaded(res); });
  }

  // ---------- SHEET (Virtual-Piano-style letter notation) ----------
  // A readable left-to-right letter stream like virtualpiano.net: each note is a
  // QWERTY letter, simultaneous notes become [chords], phrases split on |. The
  // "Playability" pass trims chords that can't be physically pressed (same-key
  // collisions / too many keys at once), keeping the bass + melody — so ANY MIDI
  // becomes playable, which VP's hand-made sheets can't do automatically. The
  // player watches it play, follows the lime highlight, and can Copy the sheet.
  const SHEET_CAP = { faith: Infinity, bal: 5, easy: 3 };
  let shLevel = "bal";
  let shRaf = 0, shPlaying = false, shPlayhead = 0, shLast = 0, shIdx = 0, shSpeedSel = 1, shLastHi = 0;
  let shTokens = [];                 // [{i,notes,chord,trim} | {bar:true}]
  const shStepEls = new Map();       // step index -> token element
  const shNotesAt = new Map();       // step index -> reduced notes (for playback)
  let shRemaining = [], shCurIdx = 0;   // play-along: notes still to press for the current token

  // The physical key a char uses, ignoring Shift, so "1" and "!" (Shift+1) collide
  // on the SAME key. charToCode already folds sharps/uppercase onto their base key.
  function sheetPhysKey(ch) { return charToCode(ch) || ("x" + ch); }

  // Trim a chord to what a hand can actually press, the way MIDI->VP converters do:
  //   1) de-duplicate notes landing on the same physical key (keep the higher one)
  //   2) cap the count, always preserving the bass (lowest) + melody (highest)
  function sheetReduce(notes, cap) {
    const byKey = new Map();
    notes.forEach((n) => {
      const k = sheetPhysKey(n.char);
      const ex = byKey.get(k);
      if (!ex || n.note > ex.note) byKey.set(k, n);
    });
    let kept = [...byKey.values()].sort((a, b) => a.note - b.note);
    if (kept.length > cap) {
      const bass = kept[0], melody = kept[kept.length - 1];
      const mids = kept.slice(1, -1).sort((a, b) => b.note - a.note);   // high -> low
      const pick = cap >= 2 ? [bass, melody] : [melody];
      for (const m of mids) { if (pick.length >= cap) break; pick.push(m); }
      kept = pick.sort((a, b) => a.note - b.note);
    }
    return kept;
  }

  // Turn prSteps into the token list at the current playability level.
  function sheetBuild() {
    shTokens = []; shNotesAt.clear();
    const steps = prSteps;
    if (!steps.length) return;
    const cap = SHEET_CAP[shLevel];
    // phrase break (|) when a gap is clearly bigger than the song's typical spacing
    const gaps = [];
    for (let i = 1; i < steps.length; i++) { const g = steps[i].t - steps[i - 1].t; if (g > 0) gaps.push(g); }
    gaps.sort((a, b) => a - b);
    const med = gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0.5;
    const barGap = Math.max(0.5, med * 3.2);
    steps.forEach((st, i) => {
      if (i > 0 && (st.t - steps[i - 1].t) >= barGap) shTokens.push({ bar: true });
      const full = st.notes;
      const notes = (cap === Infinity)
        ? full.slice().sort((a, b) => a.note - b.note)
        : sheetReduce(full, cap);
      shNotesAt.set(i, notes);
      shTokens.push({ i, notes, chord: notes.length > 1, trim: notes.length < full.length });
    });
  }

  function sheetTokenText(t) {
    if (t.bar) return "|";
    const s = t.notes.map((n) => n.char).join("");
    return t.chord ? "[" + s + "]" : s;
  }
  function sheetText() { return shTokens.map(sheetTokenText).join(" "); }

  function setSheetProgress(ratio) {
    const f = $("#shProgress"); if (f) f.style.width = Math.max(0, Math.min(1, ratio)) * 100 + "%";
  }

  // Paint the stream into #shFlow.
  function sheetRender() {
    const flow = $("#shFlow"); if (!flow) return;
    shStepEls.clear();
    if (!prSteps.length) {
      flow.innerHTML = '<div class="sh-flow-empty"><b>Pick a song to see it written in keys</b>' +
        '<span>Every note becomes a letter you can play on your keyboard.</span></div>';
      setSheetProgress(0);
      return;
    }
    sheetBuild();
    const frag = document.createDocumentFragment();
    shTokens.forEach((t) => {
      if (t.bar) {
        const b = document.createElement("span");
        b.className = "sh-bar"; b.textContent = "|";
        frag.appendChild(b); return;
      }
      const el = document.createElement("span");
      el.className = "sh-tok" + (t.chord ? " sh-chord" : "") + (t.trim ? " sh-trim" : "");
      if (t.chord) { const o = document.createElement("span"); o.className = "sh-brk"; o.textContent = "["; el.appendChild(o); }
      t.notes.forEach((n) => {
        const c = document.createElement("span");
        c.className = charNeedsShift(n.char) ? "sh-sharp" : "sh-let";
        c.textContent = n.char;
        c.dataset.note = n.note;
        el.appendChild(c);
      });
      if (t.chord) { const o = document.createElement("span"); o.className = "sh-brk"; o.textContent = "]"; el.appendChild(o); }
      frag.appendChild(el);
      shStepEls.set(t.i, el);
    });
    flow.innerHTML = ""; flow.appendChild(frag);
    flow.scrollTop = 0;
    setSheetProgress(0);
    if (!shPlaying) sheetArmStart();   // ready for play-along unless we're listening
  }

  function sheetHighlight(idx) {
    // incremental: only retire the steps passed since the last call (O(total), not O(n^2))
    for (let j = Math.max(0, shLastHi); j < idx; j++) {
      const e = shStepEls.get(j); if (e) { e.classList.add("done"); e.classList.remove("cur"); }
    }
    const cur = shStepEls.get(idx);
    if (cur) {
      cur.classList.add("cur"); cur.classList.remove("done");
      // follow the playhead, but only scroll when it nears the edges (smoother)
      const flow = $("#shFlow");
      const margin = flow.clientHeight * 0.28;
      const top = cur.offsetTop, bot = top + cur.offsetHeight;
      if (top < flow.scrollTop + margin || bot > flow.scrollTop + flow.clientHeight - margin) {
        flow.scrollTo({ top: Math.max(0, top - flow.clientHeight / 2 + cur.offsetHeight / 2), behavior: "smooth" });
      }
    }
    shLastHi = idx;
    setSheetProgress(prSteps.length > 1 ? idx / (prSteps.length - 1) : 1);
  }

  function sheetClearHL() {
    shStepEls.forEach((el) => el.classList.remove("cur", "done"));
    shLastHi = 0;
  }

  function sheetClearHits() {
    const flow = $("#shFlow"); if (!flow) return;
    flow.querySelectorAll(".hit").forEach((s) => s.classList.remove("hit"));
  }

  // ----- play-along (type the keys yourself) -----
  // Arm a token: it becomes "current" and waits for the player to press its keys.
  function sheetArm(idx) {
    shCurIdx = idx;
    const notes = shNotesAt.get(idx) || (prSteps[idx] ? prSteps[idx].notes : []);
    shRemaining = notes.map((n) => ({ note: n.note, char: n.char }));
    sheetHighlight(idx);
  }
  // (Re)start play-along from the top.
  function sheetArmStart() {
    sheetClearHL(); sheetClearHits();
    if (prSteps.length) sheetArm(0);
  }
  function sheetWrong() {
    const el = shStepEls.get(shCurIdx);
    if (el) { el.classList.remove("shake"); void el.offsetWidth; el.classList.add("shake"); }
  }
  function sheetAdvance() {
    if (shCurIdx + 1 >= prSteps.length) {     // reached the end
      const el = shStepEls.get(shCurIdx); if (el) { el.classList.remove("cur"); el.classList.add("done"); }
      setSheetProgress(1);
      shRemaining = [];
      return;
    }
    sheetArm(shCurIdx + 1);
  }
  // Register one note as pressed (from keyboard or click). Returns true if it counted.
  function sheetHitNote(note) {
    const pend = shRemaining.find((n) => n.note === note);
    if (!pend) return false;
    shRemaining.splice(shRemaining.indexOf(pend), 1);
    const el = shStepEls.get(shCurIdx);
    if (el) { const sp = el.querySelector('[data-note="' + note + '"]'); if (sp) sp.classList.add("hit"); }
    if (!shRemaining.length) sheetAdvance();
    return true;
  }
  // Keyboard input while Sheet mode is interactive (not listening).
  function onSheetKey(e) {
    if (shPlaying || !prSteps.length) return;
    const code = e.code; if (!code) return;
    // notes still pending on the current token whose physical key matches
    const cands = shRemaining.filter((n) => charToCode(n.char) === code);
    if (!cands.length) {
      if (prCodeSet.has(code)) { e.preventDefault(); sheetWrong(); }
      return;   // not a piano key (Shift, space…) — ignore
    }
    e.preventDefault();
    // a natural + its sharp can share one physical key — Shift state disambiguates
    let pick = cands[0];
    if (cands.length > 1) pick = cands.find((o) => charNeedsShift(o.char) === e.shiftKey) || cands[0];
    prPlayNote(pick.note);
    sheetHitNote(pick.note);
  }

  const SH_PLAY_ICO = '<svg viewBox="0 0 24 24" width="15" height="15"><path d="M8 5v14l11-7-11-7z" fill="currentColor"/></svg>';
  const SH_STOP_ICO = '<svg viewBox="0 0 24 24" width="15" height="15"><rect x="6" y="5" width="12" height="12" rx="2" fill="currentColor"/></svg>';
  function updateSheetPlayBtn() {
    const b = $("#shPlay"); if (!b) return;
    b.classList.toggle("playing", shPlaying);
    b.innerHTML = (shPlaying ? SH_STOP_ICO + " <span>Stop</span>" : SH_PLAY_ICO + " <span>Listen</span>");
  }

  function sheetStop() {
    shPlaying = false;
    if (shRaf) cancelAnimationFrame(shRaf); shRaf = 0;
    stopPracticeNotes();
    sheetClearHL(); sheetClearHits();
    setSheetProgress(0);
    updateSheetPlayBtn();
  }

  function sheetStart() {
    if (prMode !== "sheet" || !prSteps.length) return;
    sheetStop();
    ensurePracticeAudio();
    shIdx = 0; shLast = 0;
    shPlayhead = (prSteps[0].t || 0) - 0.35;
    shPlaying = true;
    updateSheetPlayBtn();
    shRaf = requestAnimationFrame(sheetFrame);
  }

  function sheetFrame(ts) {
    const now = ts / 1000;
    const dt = shLast ? Math.min(0.05, now - shLast) : 0;
    shLast = now;
    shPlayhead += dt * shSpeedSel;
    let played = -1;
    while (shIdx < prSteps.length && prSteps[shIdx].t <= shPlayhead) {
      const notes = shNotesAt.get(shIdx) || prSteps[shIdx].notes;
      notes.forEach((n) => prPlayNote(n.note));
      played = shIdx;
      shIdx++;
    }
    if (played >= 0) sheetHighlight(played);
    if (shIdx >= prSteps.length && shPlayhead > (prSteps[prSteps.length - 1].t + 0.5)) {
      shPlaying = false; if (shRaf) cancelAnimationFrame(shRaf); shRaf = 0;
      updateSheetPlayBtn();
      sheetArmStart();        // demo over — hand control back for play-along
      return;
    }
    shRaf = requestAnimationFrame(sheetFrame);
  }

  // Show the Sheet panel + render (used by the mode switch and on view re-entry).
  function enterSheet() {
    prMode = "sheet";
    sheetStop(); stopRhythm(); freePlayStop(); clearFreeTrails();
    $("#prEmpty").hidden = true;
    $("#prResult").hidden = true; $("#prResult").innerHTML = "";
    $("#prConfetti").hidden = true; $("#prConfetti").innerHTML = "";
    $("#prGame").hidden = true; $("#prHud").hidden = true;
    $("#prTrainer").hidden = true; $("#prFoot").hidden = true;
    $("#prSheet").hidden = false;
    ensurePracticeAudio();
    if (prKeymap && Object.keys(prKeymap).length) {
      prMapChars = new Set(Object.values(prKeymap));
      prCodeSet = new Set([...prMapChars].map(charToCode).filter(Boolean));
    }
    if (prSteps.length) prLoaded = true;
    prRunning = true;
    const sel = $("#shSpeed"); shSpeedSel = sel ? (parseFloat(sel.value) || 1) : 1;
    sheetRender();
    updateSheetPlayBtn();
    const a = api(); if (a && a.practiceActive) a.practiceActive(true);
  }

  // A freshly chosen song while Sheet mode is active.
  function sheetLoadSong(res) {
    prSteps = res.steps || [];
    if (res.keymap) prKeymap = res.keymap;
    prMapChars = new Set(Object.values(prKeymap));
    prCodeSet = new Set([...prMapChars].map(charToCode).filter(Boolean));
    prSongKey = res.name || "";
    prDuration = res.duration || 0;
    prCurrentPath = res.path || prCurrentPath;
    prLoaded = true;
    sheetStop();
    $("#prEmpty").hidden = true; $("#prSheet").hidden = false;
    sheetRender();
  }

  // ---------- LIVE VISUALIZER / STAGE MODE ----------
  // A full-window falling-notes view synced to the Player's playback timeline.
  // Reuses the practice piano look but is fully self-contained so it can't break
  // the trainer. Driven by "timeline" events + wallclock interpolation.
  let sgOpen = false, sgRaf = 0, sgSteps = [], sgPath = "";
  let sgKeymap = {}, sgWhiteW = 30;
  let sgLastSec = 0, sgLastWall = 0, sgSpeed = 1, sgPlaying = false, sgPlayhead = 0;
  let sgMin = 21, sgMax = 108;
  const sgNoteX = {}, sgKeyEls = {}, sgTiles = new Map();
  let sgFlashIx = 0;
  const SG_LOOKAHEAD = 2.6;
  const sgCharForNote = (n) => sgKeymap[n] != null ? sgKeymap[n] : sgKeymap[String(n)];

  function stageBuildPiano(minNote, maxNote) {
    let lo = Math.max(0, minNote - 1), hi = Math.min(127, maxNote + 1);
    while (isSharp(lo) && lo > 0) lo--;
    while (isSharp(hi) && hi < 127) hi++;
    const wrap = $("#sgStage"), avail = Math.max(360, (wrap.parentElement.clientWidth || 1000) - 4);
    let whiteCount = 0;
    for (let n = lo; n <= hi; n++) if (!isSharp(n)) whiteCount++;
    sgWhiteW = Math.max(16, Math.min(64, Math.floor(avail / Math.max(1, whiteCount))));
    const pianoWidth = whiteCount * sgWhiteW;
    const off = Math.max(0, (avail - pianoWidth) / 2);
    const fullW = Math.max(pianoWidth, avail);
    const blackW = Math.round(sgWhiteW * 0.62);
    const ph = Math.round(Math.min(220, Math.max(140, sgWhiteW * 3.2)));
    wrap.style.width = fullW + "px";
    wrap.style.setProperty("--ph", ph + "px");
    wrap.style.setProperty("--slot", "46px");
    const piano = $("#sgPiano"); piano.innerHTML = "";
    for (const k in sgNoteX) delete sgNoteX[k];
    for (const k in sgKeyEls) delete sgKeyEls[k];
    let wi = 0;
    for (let n = lo; n <= hi; n++) {
      const white = !isSharp(n);
      const el = document.createElement("div");
      let x;
      if (white) { const left = off + wi * sgWhiteW; el.className = "pk pk-white"; el.style.left = left + "px"; el.style.width = sgWhiteW + "px"; x = left + sgWhiteW / 2; wi++; }
      else { const c = off + wi * sgWhiteW; el.className = "pk pk-black"; el.style.left = (c - blackW / 2) + "px"; el.style.width = blackW + "px"; x = c; }
      sgNoteX[n] = x;
      const ch = sgCharForNote(n);
      if (ch != null) { const lbl = document.createElement("span"); lbl.className = "pk-lbl"; lbl.textContent = ch; el.appendChild(lbl); }
      sgKeyEls[n] = el; piano.appendChild(el);
    }
    const lanes = $("#sgLanes"); lanes.innerHTML = "";
    for (let i = 0; i <= whiteCount; i++) { const ln = document.createElement("div"); ln.className = "hw-lane"; ln.style.left = (off + i * sgWhiteW) + "px"; lanes.appendChild(ln); }
  }

  function stageLoad(path) {
    const a = api(); if (!a || !a.practiceLoad || !path) return;
    a.practiceLoad(path).then((res) => {
      if (!res || !res.ok) { sgSteps = []; $("#sgEmpty").hidden = false; return; }
      sgPath = path; sgSteps = res.steps || []; sgKeymap = res.keymap || {};
      sgMin = res.minNote; sgMax = res.maxNote;
      sgFlashIx = 0; sgTiles.clear(); $("#sgTrack").innerHTML = "";
      $("#sgTitle").textContent = cleanName(res.name || "");
      $("#sgEmpty").hidden = true;
      stageBuildPiano(res.minNote, res.maxNote);
      if (state) { sgLastSec = 0; sgLastWall = performance.now(); }
    });
  }

  function stageSync(sec) {
    sgLastSec = sec || 0; sgLastWall = performance.now();
    // drop a flashed marker back if the user seeked backwards
    while (sgFlashIx > 0 && sgSteps[sgFlashIx - 1] && sgSteps[sgFlashIx - 1].t > sgLastSec + 0.05) sgFlashIx--;
  }

  function stageStateChanged() {
    if (!sgOpen) return;
    sgPlaying = !!(state && state.isRunning && !state.paused);
    sgSpeed = (state && state.speed ? state.speed : 100) / 100;
    const playing = state && state.isRunning && state.playingFile;
    if (playing && state.playingFile !== sgPath) stageLoad(state.playingFile);
    else if (!playing) { $("#sgEmpty").hidden = false; sgSteps = []; $("#sgTrack").innerHTML = ""; sgTiles.clear(); }
  }

  function sgFrame() {
    if (!sgOpen) { sgRaf = 0; return; }            // never spin while the stage is closed
    if (!sgSteps.length) { sgRaf = requestAnimationFrame(sgFrame); return; }
    const now = performance.now();
    sgPlayhead = sgPlaying ? sgLastSec + ((now - sgLastWall) / 1000) * sgSpeed : sgLastSec;
    const track = $("#sgTrack");
    const pps = (track.clientHeight || 360) / SG_LOOKAHEAD;
    const lo = sgPlayhead - 0.5, hi = sgPlayhead + SG_LOOKAHEAD + 0.1;
    sgTiles.forEach((el, i) => { const t = sgSteps[i] && sgSteps[i].t; if (t == null || t < lo || t > hi) { el.remove(); sgTiles.delete(i); } });
    for (let i = 0; i < sgSteps.length; i++) {
      const st = sgSteps[i]; if (st.t < lo) continue; if (st.t > hi) break;
      let el = sgTiles.get(i);
      if (!el) {
        el = document.createElement("div"); el.className = "ry-tile";
        st.notes.forEach((note) => { const s = document.createElement("span"); s.className = "hw-note" + (isSharp(note.note) ? " sharp" : ""); s.style.setProperty("--x", sgNoteX[note.note] || 0); s.textContent = note.char; el.appendChild(s); });
        track.appendChild(el); sgTiles.set(i, el);
      }
      el.style.bottom = ((st.t - sgPlayhead) * pps) + "px";
    }
    // flash keys (and play the piano) as notes cross the hit line
    while (sgFlashIx < sgSteps.length && sgSteps[sgFlashIx].t <= sgPlayhead) {
      // only sound notes that just crossed — a big forward seek can catch up
      // many steps at once, and we don't want to blast them all
      const fresh = sgPlaying && (sgPlayhead - sgSteps[sgFlashIx].t) < 0.25;
      sgSteps[sgFlashIx].notes.forEach((n) => {
        const k = sgKeyEls[n.note]; if (k) { k.classList.add("hit"); setTimeout(() => k.classList.remove("hit"), 170); }
        // when the Settings sound is on, the backend already voices the song
        // (mic illusion); otherwise play the stage piano ourselves
        if (fresh && !soundOn) prPlayNote(n.note);
      });
      const tile = sgTiles.get(sgFlashIx); if (tile) tile.classList.add("ry-hit");
      sgFlashIx++;
    }
    sgRaf = requestAnimationFrame(sgFrame);
  }

  function stageOpen() {
    sgOpen = true;
    $("#stageOverlay").hidden = false;
    document.body.classList.add("stage-on");
    // prep the piano so the stage can voice notes even when the mic-illusion
    // sound is off (the click that opened the stage is our audio gesture)
    ensureCtx(); loadPiano();
    stageStateChanged();
    if (state && state.isRunning && state.playingFile && state.playingFile !== sgPath) stageLoad(state.playingFile);
    sgLastWall = performance.now();
    if (!sgRaf) sgRaf = requestAnimationFrame(sgFrame);
  }

  function stageClose() {
    sgOpen = false;
    if (sgRaf) cancelAnimationFrame(sgRaf); sgRaf = 0;
    $("#stageOverlay").hidden = true;
    document.body.classList.remove("stage-on");
  }

  let isFullscreen = false;
  function toggleFullscreen() {
    const a = api(); if (!a || !a.toggleFullscreen) return;
    a.toggleFullscreen(); isFullscreen = !isFullscreen;
  }

  // ---------- wire up ----------
  function bind() {
    $$(".nav").forEach((n) => n.addEventListener("click", () => switchView(n.dataset.view)));

    $$(".mode-opt").forEach((o) =>
      o.addEventListener("click", () => setMode(o.dataset.mode, true)));

    $("#openBtn").addEventListener("click", () => call("chooseFile"));
    $("#recentSelect").addEventListener("change", (e) => { if (e.target.value) call("setFile", e.target.value); });
    $("#deviceSelect").addEventListener("change", (e) => call("setOutputDevice", e.target.value));

    $("#playBtn").addEventListener("click", () => call("toggle"));
    $("#stopBtn").addEventListener("click", () => call("stop"));
    $("#prevBtn").addEventListener("click", () => call("prevTrack"));
    $("#nextBtn").addEventListener("click", () => call("nextTrack"));
    $("#switchBtn").addEventListener("click", () => call("play"));
    $("#queueClear").addEventListener("click", () => call("clearQueue"));

    $("#soundToggle").addEventListener("click", () => {
      const on = !soundOn;
      soundOn = on;
      $("#soundToggle").textContent = on ? "On" : "Off";
      $("#soundToggle").classList.toggle("on", on);
      if (on) ensureAudio();
      const a = api(); if (a && a.setSound) a.setSound("enabled", on);
    });
    $$("#soundMode .seg-opt").forEach((o) => o.addEventListener("click", () => {
      soundMode = o.dataset.smode;
      $$("#soundMode .seg-opt").forEach((x) => x.classList.toggle("active", x === o));
      const pr = $("#soundPackRow"); if (pr) pr.hidden = soundMode !== "keyboard";
      stopAllNotes();
      if (soundOn) ensureAudio();
      const a = api(); if (a && a.setSound) a.setSound("mode", soundMode);
    }));
    $("#soundPack").addEventListener("change", (e) => {
      currentPackId = e.target.value;
      stopAllNotes();
      if (soundOn) ensureAudio();   // triggers loadPack(currentPackId)
      const a = api(); if (a && a.setSound) a.setSound("pack", currentPackId);
    });

    $$("#humProfile .seg-opt").forEach((o) => o.addEventListener("click", () => {
      $$("#humProfile .seg-opt").forEach((x) => x.classList.toggle("active", x === o));
      const on = o.dataset.hum !== "off";
      const box = $("#humSliders"); if (box) { box.style.opacity = on ? "1" : ".4"; box.style.pointerEvents = on ? "" : "none"; }
      const a = api(); if (a && a.setHumanize) a.setHumanize("profile", o.dataset.hum);
    }));
    HUM_KEYS.forEach((k) => {
      const el = $("#" + humId(k)); if (!el) return;
      el.addEventListener("input", () => {
        el.style.setProperty("--fill", el.value + "%");
        const lab = $("#" + humId(k) + "Val"); if (lab) lab.textContent = el.value;
        // editing a slider means it's no longer a named preset
        $$("#humProfile .seg-opt").forEach((x) => x.classList.remove("active"));
      });
      el.addEventListener("change", () => { const a = api(); if (a && a.setHumanize) a.setHumanize(k, parseInt(el.value)); });
    });

    const rfTog = $("#rfToggle");
    if (rfTog) rfTog.addEventListener("click", () => {
      const on = !rfTog.classList.contains("on");
      rfTog.classList.toggle("on", on);
      rfTog.textContent = on ? "On" : "Off";
      const box = $("#rfSliders"); if (box) { box.style.opacity = on ? "1" : ".4"; box.style.pointerEvents = on ? "" : "none"; }
      const a = api(); if (a && a.setRandomFail) a.setRandomFail("enabled", on);
    });
    RF_KEYS.forEach(([k, id]) => {
      const el = $("#" + id); if (!el) return;
      el.addEventListener("input", () => {
        el.style.setProperty("--fill", el.value + "%");
        const lab = $("#" + id + "Val"); if (lab) lab.textContent = el.value;
      });
      el.addEventListener("change", () => { const a = api(); if (a && a.setRandomFail) a.setRandomFail(k, parseInt(el.value)); });
    });

    const ut = $("#updateToast");
    if (ut) {
      $("#utClose").addEventListener("click", () => { ut.hidden = true; });
      $("#utNotes").addEventListener("click", () => {
        const a = api(); if (a && a.openRelease && updateInfo) a.openRelease(updateInfo.url);
      });
      $("#utDl").addEventListener("click", () => {
        const a = api(); if (!a || !updateInfo) return;
        const btn = $("#utDl");
        if (updateInfo.asset && a.downloadUpdate) {
          btn.disabled = true; btn.textContent = "Downloading…";
          a.downloadUpdate(updateInfo.asset, updateInfo.tag || "").then((res) => {
            if (res && res.ok) {
              btn.textContent = "Saved ✓";
              const sub = $("#utSub"); if (sub) sub.textContent = "Saved to Downloads — extract it and replace your Velo folder.";
            } else {
              btn.disabled = false; btn.textContent = "Download";
              if (a.openRelease) a.openRelease(updateInfo.url);
            }
          }).catch(() => { btn.disabled = false; btn.textContent = "Download"; });
        } else if (a.openRelease) {
          a.openRelease(updateInfo.url);
        }
      });
    }

    const sl = $("#speedSlider"), inp = $("#speedInput");
    sl.addEventListener("input", () => { setSpeedUI(parseInt(sl.value)); });
    sl.addEventListener("change", () => call("setSpeed", parseInt(sl.value)));
    inp.addEventListener("change", () => { const v = parseInt(inp.value) || 100; call("setSpeed", v); });
    $("#speedDown").addEventListener("click", () => call("changeSpeed", -5));
    $("#speedUp").addEventListener("click", () => call("changeSpeed", 5));

    $$("#chips .chip").forEach((c) =>
      c.addEventListener("click", () => {
        const on = !c.classList.contains("on");
        c.classList.toggle("on", on);
        call("setOption", c.dataset.opt, on);
      }));

    $("#clearLog").addEventListener("click", () => { $("#log").innerHTML = ""; });

    $("#winPin").addEventListener("click", () => {
      const on = !$("#winPin").classList.contains("on");
      $("#winPin").classList.toggle("on", on);
      const a = api(); if (a && a.setOnTop) a.setOnTop(on);
    });
    const osb = $("#openStage"); if (osb) osb.addEventListener("click", stageOpen);
    const sxb = $("#sgExit"); if (sxb) sxb.addEventListener("click", stageClose);
    const sfb = $("#sgFull"); if (sfb) sfb.addEventListener("click", toggleFullscreen);
    document.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      if (isFullscreen) toggleFullscreen();
      else if (sgOpen) stageClose();
    });

    $("#winMin").addEventListener("click", () => call("minimize"));
    $("#winMax").addEventListener("click", () => call("maximize"));
    $("#winClose").addEventListener("click", () => call("close"));

    // Frameless resize grips → hand off to Windows' native resize loop. Don't
    // capture the pointer here, or the OS loop won't receive the drag.
    document.querySelectorAll(".rsz").forEach((g) => {
      g.addEventListener("pointerdown", (e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        call("startResize", g.dataset.edge);
      });
    });

    const scrub = $("#scrub");
    const scrubRatio = (e) => {
      const r = scrub.getBoundingClientRect();
      return Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    };
    const scrubPreview = (rt) => { setScrub(rt); if (scrubbingTotal) $("#tCur").textContent = fmt(rt * scrubbingTotal); };
    scrub.addEventListener("pointerdown", (e) => {
      if (!state || !state.isRunning || !scrubbingTotal) return;
      scrubDragging = true;
      try { scrub.setPointerCapture(e.pointerId); } catch (_) {}
      scrubPreview(scrubRatio(e));
    });
    scrub.addEventListener("pointermove", (e) => { if (scrubDragging) scrubPreview(scrubRatio(e)); });
    scrub.addEventListener("pointerup", (e) => {
      if (!scrubDragging) return;
      scrubDragging = false;
      call("seek", Math.round(scrubRatio(e) * scrubbingTotal));
    });

    $("#queueAdd").addEventListener("click", () => call("queueAdd"));

    // --- practice ---
    $("#prOpen").addEventListener("click", practiceChooseFile);
    $("#prStart").addEventListener("click", practiceChooseFile);
    $("#prPianoSel").addEventListener("change", (e) => {
      setPiano(e.target.value);
      ensurePracticeAudio();
      const a = api(); if (a && a.setSound) a.setSound("piano", e.target.value);
    });
    $("#prSong").addEventListener("change", (e) => {
      const v = e.target.value;
      if (v === "__none__") {
        if (prMode === "free") freeClearSong();
        else if (prMode === "sheet") { prSteps = []; prSongKey = ""; sheetStop(); sheetRender(); }
        else { prSteps = []; prLoaded = false; showPracticeEmpty(); }
        return;
      }
      if (!v) return;
      const a = api(); if (!a || !a.practiceLoad) return;
      a.practiceLoad(v).then((res) => { if (res) applyLoaded(res); });
    });
    $("#prFreePlay").addEventListener("click", freePlayToggle);
    $("#prRestart").addEventListener("click", () => { if (prLoaded) restartPractice(); });

    // --- sheet mode ---
    $("#shPlay").addEventListener("click", () => {
      if (shPlaying) { sheetStop(); sheetArmStart(); }   // stop the demo, hand back for play-along
      else sheetStart();
    });
    $("#shSpeed").addEventListener("change", (e) => { shSpeedSel = parseFloat(e.target.value) || 1; });
    // click a letter to hear it — and if it's the current note, it counts as played
    $("#shFlow").addEventListener("click", (e) => {
      if (shPlaying) return;
      const sp = e.target.closest("[data-note]"); if (!sp) return;
      const note = parseInt(sp.dataset.note, 10); if (isNaN(note)) return;
      ensurePracticeAudio();
      prPlayNote(note);
      const tok = sp.closest(".sh-tok");
      if (tok && tok === shStepEls.get(shCurIdx)) sheetHitNote(note);
    });
    $$("#shLevel .seg-opt").forEach((o) => o.addEventListener("click", () => {
      if (o.dataset.shlevel === shLevel) return;
      shLevel = o.dataset.shlevel;
      $$("#shLevel .seg-opt").forEach((x) => x.classList.toggle("active", x === o));
      const wasPlaying = shPlaying;
      sheetStop();
      sheetRender();
      if (wasPlaying) sheetStart();
    }));
    $("#shCopy").addEventListener("click", () => {
      if (!prSteps.length) return;
      const txt = sheetText();
      const ok = () => {
        const b = $("#shCopy"), s = b.querySelector("span"); if (!s) return;
        const prev = s.textContent; b.classList.add("ok"); s.textContent = "Copied!";
        setTimeout(() => { b.classList.remove("ok"); s.textContent = prev; }, 1400);
      };
      const fallback = () => {
        try {
          const ta = document.createElement("textarea");
          ta.value = txt; ta.style.position = "fixed"; ta.style.opacity = "0";
          document.body.appendChild(ta); ta.select();
          document.execCommand("copy"); document.body.removeChild(ta); ok();
        } catch (_) {}
      };
      try {
        if (navigator.clipboard && navigator.clipboard.writeText)
          navigator.clipboard.writeText(txt).then(ok).catch(fallback);
        else fallback();
      } catch (_) { fallback(); }
    });

    $$("#prModeSwitch .seg-opt").forEach((o) => o.addEventListener("click", () => {
      if (o.dataset.pmode === prMode) return;
      prMode = o.dataset.pmode;
      $$("#prModeSwitch .seg-opt").forEach((x) => x.classList.toggle("active", x === o));
      sheetStop();                       // leaving any mode: kill a running sheet
      $("#prSheet").hidden = true;        // hidden by default; enterSheet re-shows it
      if (prMode === "free") enterFree();
      else if (prMode === "sheet") enterSheet();
      else if (prSteps.length) restartPractice();
      else showPracticeEmpty();
    }));
    $("#prSpeed").addEventListener("change", (e) => {
      prSpeedSel = parseFloat(e.target.value) || 1;
      if (prLoaded && prMode === "rhythm" && !RY_TRAINER.on) restartPractice();
    });
    $("#trToggle").addEventListener("click", () => {
      RY_TRAINER.on = !RY_TRAINER.on; trLadderIx = 0;
      renderTrainerRange();
      if (prLoaded) restartPractice();
    });
    const trf = $("#trFrom"), trt = $("#trTo");
    const applyTrainer = () => {
      RY_TRAINER.on = true; trLadderIx = 0;
      let a = parseInt(trf.value) || 0, b = parseInt(trt.value) || 0;
      if (a > b) { const t = a; a = b; b = t; }
      RY_TRAINER.from = a; RY_TRAINER.to = b;
      renderTrainerRange();
    };
    trf.addEventListener("input", applyTrainer);
    trt.addEventListener("input", applyTrainer);
    const trCommit = () => { if (prLoaded) restartPractice(); };
    trf.addEventListener("change", trCommit);
    trt.addEventListener("change", trCommit);

    document.addEventListener("keydown", onPracticeKey, true);
    document.addEventListener("keyup", (e) => { if (prMode === "free" && prRunning) onFreeKeyUp(e); }, true);
    // Free-play mouse: click a key to play it, or hold and DRAG across keys to
    // glide (glissando) — each key the cursor enters plays automatically.
    const ppiano = $("#prPiano");
    if (ppiano) {
      let glissNote = null;
      const noteAt = (e) => {
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const k = el && el.closest ? el.closest(".pk") : null;
        if (!k) return null;
        const n = parseInt(k.dataset.note, 10);
        return isNaN(n) ? null : n;
      };
      const leaveKey = (n) => {
        if (n == null) return;
        if (!noteHeld(n)) { const pk = prKeyEls[n]; if (pk) pk.classList.remove("hit"); }
        releaseTrail("mouse");
      };
      // a quick blip for keys the cursor swept past between two move events
      const tapNote = (n) => {
        if (prNoteX[n] == null) return;
        prPlayNote(n);
        const pk = prKeyEls[n];
        if (pk) { pk.classList.add("hit"); setTimeout(() => { if (!noteHeld(n)) pk.classList.remove("hit"); }, 150); }
        spawnReleasedTrail(n, 64);   // a visible ribbon for the swept key
      };
      const setGliss = (n) => {
        if (n === glissNote) return;
        // fill in keys skipped between the last and new position — but only of
        // the SAME row the cursor is sweeping (white→whites), so a glide along
        // the white keys doesn't also fire every sharp in between.
        if (glissNote != null && n != null && Math.abs(n - glissNote) <= 40) {
          const step = n > glissNote ? 1 : -1;
          for (let m = glissNote + step; m !== n; m += step) {
            if (isSharp(m) === isSharp(n)) tapNote(m);
          }
        }
        leaveKey(glissNote);
        glissNote = n;
        if (n != null) {
          prPlayNote(n);
          const pk = prKeyEls[n]; if (pk) pk.classList.add("hit");
          startTrail("mouse", n);
        }
      };
      const onMove = (e) => { if (prMode === "free" && prRunning) setGliss(noteAt(e)); };
      const endGliss = () => {
        leaveKey(glissNote); glissNote = null;
        window.removeEventListener("pointermove", onMove);
      };
      ppiano.addEventListener("pointerdown", (e) => {
        if (prMode !== "free" || !prRunning) return;
        const n = noteAt(e); if (n == null) return;
        setGliss(n);
        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", endGliss, { once: true });
      });
    }

    // F11 toggles real OS fullscreen (covers the taskbar) — great for streaming.
    document.addEventListener("keydown", (e) => {
      if (e.key === "F11") { e.preventDefault(); toggleFullscreen(); }
    });

    // Responsive: rebuild the pianos whenever their container resizes (window
    // maximize, fullscreen, snap, monitor change) — not just on load.
    if (window.ResizeObserver) {
      let prTimer, sgTimer;
      new ResizeObserver(() => {
        if (!prLoaded) return;
        const v = document.querySelector('.view[data-view="practice"]');
        if (!v || v.hidden) return;
        clearTimeout(prTimer); prTimer = setTimeout(rebuildPracticeLayout, 150);
      }).observe($("#prGame"));
      new ResizeObserver(() => {
        if (!sgOpen || !sgSteps.length) return;
        clearTimeout(sgTimer); sgTimer = setTimeout(() => {
          stageBuildPiano(sgMin, sgMax);
          sgTiles.forEach((el) => el.remove()); sgTiles.clear(); $("#sgTrack").innerHTML = "";
        }, 150);
      }).observe($("#stageOverlay"));
    }

    let hubSearchTimer;
    $("#hubSearch").addEventListener("input", () => {
      clearTimeout(hubSearchTimer);
      hubSearchTimer = setTimeout(() => {
        if (hubSource === "bitmidi") loadBit($("#hubSearch").value);
        else if (hubSource === "onlineseq") loadOnlineSeq($("#hubSearch").value);
        else applyHubFilter();
      }, hubSource === "nanomidi" ? 250 : 400);
    });
    $("#hubSort").addEventListener("change", () => { if (hubSource === "nanomidi") applyHubFilter(); });
    $("#hubSource").addEventListener("change", (e) => {
      hubSource = e.target.value;
      $("#hubSort").disabled = (hubSource !== "nanomidi");   // sort only applies to the nanoMIDI client-side list
      hubLoaded = false;
      loadHub();
    });
    $("#hubPrev").addEventListener("click", () => {
      if (hubSource === "bitmidi") { if (bitPage > 0) loadBit(null, bitPage - 1); }
      else if (hubPage > 1) { hubPage--; renderHub(); }
    });
    $("#hubNext").addEventListener("click", () => {
      if (hubSource === "bitmidi") { if (bitPage + 1 < hubTotalPages()) loadBit(null, bitPage + 1); }
      else { hubPage++; renderHub(); }
    });

    // --- drums ---
    $("#drumsOpen").addEventListener("click", () => api().drumsChoose().then(applyDrumsState));
    $("#drumsRecent").addEventListener("change", (e) => { if (e.target.value) api().drumsSetFile(e.target.value).then(applyDrumsState); });
    $("#drumsPlay").addEventListener("click", () => api().drumsToggle().then(applyDrumsState));
    $("#drumsStop").addEventListener("click", () => api().drumsStop().then(applyDrumsState));
    const dsl = $("#drumsSlider"), dinp = $("#drumsSpeedInput");
    dsl.addEventListener("input", () => { dinp.value = dsl.value; dsl.style.setProperty("--fill", (((dsl.value - dsl.min) / (dsl.max - dsl.min)) * 100) + "%"); });
    dsl.addEventListener("change", () => api().drumsSetSpeed(parseInt(dsl.value)).then(applyDrumsState));
    dinp.addEventListener("change", () => api().drumsSetSpeed(parseInt(dinp.value) || 100).then(applyDrumsState));
    $("#drumsSpeedDown").addEventListener("click", () => api().drumsChangeSpeed(-5).then(applyDrumsState));
    $("#drumsSpeedUp").addEventListener("click", () => api().drumsChangeSpeed(5).then(applyDrumsState));
    $("#drumsClearLog").addEventListener("click", () => { $("#drumsLog").innerHTML = ""; });
    $$("#drumsChips .chip").forEach((c) => c.addEventListener("click", () => {
      const on = !c.classList.contains("on"); c.classList.toggle("on", on);
      api().drumsSetOption(c.dataset.opt, on).then(applyDrumsState);
    }));

    // --- midi -> keys ---
    $("#inputToggle").addEventListener("click", () => api().inputToggle().then(applyInputState));
    $("#inputRefresh").addEventListener("click", () => api().inputState().then(applyInputState));
    $("#inputDevice").addEventListener("change", (e) => api().inputSetDevice(e.target.value).then(applyInputState));
    $("#inputClearLog").addEventListener("click", () => { $("#inputLog").innerHTML = ""; });
    $$("#inputChips .chip").forEach((c) => c.addEventListener("click", () => {
      const on = !c.classList.contains("on"); c.classList.toggle("on", on);
      api().inputSetOption(c.dataset.opt, on).then(applyInputState);
    }));

    // --- hotkeys ---
    $$(".hk-key").forEach((b) => b.addEventListener("click", () => startCapture(b)));
    document.addEventListener("keydown", (e) => {
      if (!capturing) return;
      e.preventDefault();
      const name = jsKeyToName(e);
      const btn = capturing; capturing = null; btn.classList.remove("capturing");
      if (name) api().setHotkey(btn.dataset.action, name).then((s) => applyHotkeys(s.hotkeys));
      else applyHotkeys(inputStateHotkeysFallback());
    });
  }

  function inputStateHotkeysFallback() {
    return (state && state.hotkeys) || {};
  }

  function hideSplash() {
    const s = $("#splash");
    if (s) s.classList.add("gone");
  }

  function hasFiles(e) {
    const t = e.dataTransfer && e.dataTransfer.types;
    return t && Array.prototype.indexOf.call(t, "Files") !== -1;
  }

  function setupDragDrop() {
    let depth = 0;
    window.addEventListener("dragenter", (e) => { if (!hasFiles(e)) return; e.preventDefault(); depth++; document.body.classList.add("dragging"); });
    window.addEventListener("dragover", (e) => { if (hasFiles(e)) e.preventDefault(); });
    window.addEventListener("dragleave", (e) => { if (!hasFiles(e)) return; e.preventDefault(); depth--; if (depth <= 0) { depth = 0; document.body.classList.remove("dragging"); } });
    window.addEventListener("drop", (e) => {
      if (!hasFiles(e)) return;
      e.preventDefault(); depth = 0; document.body.classList.remove("dragging");
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f || !/\.midi?$/i.test(f.name)) return;
      const reader = new FileReader();
      reader.onload = () => {
        const a = api(); if (!a || !a.loadMidiBytes) return;
        const active = document.querySelector(".nav.active");
        const target = active && active.dataset.view === "drums" ? "drums" : "player";
        a.loadMidiBytes(f.name, reader.result, target).then((res) => {
          if (res && res.ok) {
            if (res.target === "drums") { applyDrumsState(res.state); switchView("drums"); }
            else { applyState(res.state); switchView("player"); }
          }
        });
      };
      reader.readAsDataURL(f);
    });
  }

  function init() {
    bind();
    setupDragDrop();
    refreshDiscordAvatar();
    call("getState").then(() => {
      setMode(state && state.options && state.options.useMIDIOutput ? "midi" : "qwerty", false);
      hideSplash();   // always start on the Player (the home tab)
    });
    setTimeout(hideSplash, 3000);
  }

  if (api()) init();
  else window.addEventListener("pywebviewready", init);
})();

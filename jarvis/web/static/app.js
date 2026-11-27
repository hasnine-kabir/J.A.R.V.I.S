/* J.A.R.V.I.S. web UI — vanilla JS, no build step. */
(() => {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  const ui = {
    messages: $("#messages"), empty: $("#empty"), input: $("#input"), form: $("#composer"),
    send: $("#send-btn"), mic: $("#mic-btn"), stop: $("#stop-btn"),
    voice: $("#toggle-voice"), handsfree: $("#toggle-handsfree"), hfHint: $("#hf-hint"),
    model: $("#model-select"), conn: $("#conn"), stateLabel: $("#state-label"),
    greeting: $("#greeting"), emptyTitle: $("#empty-title"), version: $("#version"),
    keys: $("#keys-list"), skills: $("#skills-list"), skillsCount: $("#skills-count"),
    facts: $("#facts-list"), notes: $("#notes-list"), activity: $("#activity-list"),
    left: $("#rail-left"), right: $("#rail-right"), scrim: $("#scrim"),
    dialog: $("#confirm-dialog"), toasts: $("#toasts"),
  };

  let ws = null;
  let retry = 0;
  let status = {};
  let state = "offline";
  let historyLoaded = false;
  const turns = new Map(); // turn id -> { root, text, tools, raw, frame }
  let pendingConfirm = null;

  // ---------------------------------------------------------------- markdown (small + safe)
  const esc = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function inline(s) {
    const codes = [];
    s = esc(s).replace(/`([^`\n]+)`/g, (_, c) => `\u0000${codes.push(c) - 1}\u0000`);
    s = s
      .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
      .replace(/(^|[\s(])(https?:\/\/[^\s<)]+[^\s<).,;:!?])/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>')
      .replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>")
      .replace(/(^|[^_\w])_([^_\n]+)_(?!\w)/g, "$1<em>$2</em>");
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
  }

  function blocks(src) {
    const lines = src.split("\n");
    const html = [];
    let para = [];
    let list = null; // { tag, items }
    const flushPara = () => { if (para.length) { html.push(`<p>${para.map(inline).join("<br>")}</p>`); para = []; } };
    const flushList = () => { if (list) { html.push(`<${list.tag}>${list.items.map((i) => `<li>${inline(i)}</li>`).join("")}</${list.tag}>`); list = null; } };
    for (const line of lines) {
      let m;
      if (!line.trim()) { flushPara(); flushList(); continue; }
      if ((m = line.match(/^\s*(#{1,4})\s+(.*)$/))) {
        flushPara(); flushList();
        const level = Math.min(3, m[1].length);
        html.push(`<h${level}>${inline(m[2])}</h${level}>`);
      } else if ((m = line.match(/^\s*[-*•]\s+(.*)$/)) || (m = line.match(/^\s*\d+[.)]\s+(.*)$/))) {
        flushPara();
        const tag = /^\s*\d/.test(line) ? "ol" : "ul";
        if (!list || list.tag !== tag) { flushList(); list = { tag, items: [] }; }
        list.items.push(m[1]);
      } else if ((m = line.match(/^>\s?(.*)$/))) {
        flushPara(); flushList();
        html.push(`<blockquote>${inline(m[1])}</blockquote>`);
      } else {
        if (list && /^\s{2,}/.test(line)) { list.items[list.items.length - 1] += " " + line.trim(); continue; }
        flushList();
        para.push(line);
      }
    }
    flushPara(); flushList();
    return html.join("");
  }

  function markdown(src) {
    return src.split("```").map((part, i) => {
      if (i % 2 === 0) return blocks(part);
      const nl = part.indexOf("\n");
      const code = nl >= 0 ? part.slice(nl + 1) : part;
      return `<pre><button class="copy" type="button">Copy</button><code>${esc(code.replace(/\n$/, ""))}</code></pre>`;
    }).join("");
  }

  // ---------------------------------------------------------------- helpers
  const timeStr = (d = new Date()) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const prettyTool = (name) => name.replace("__", " → ").replace(/_/g, " ");

  function nearBottom() {
    const m = ui.messages;
    return m.scrollHeight - m.scrollTop - m.clientHeight < 140;
  }
  function scrollDown(force = false) {
    if (force || nearBottom()) ui.messages.scrollTop = ui.messages.scrollHeight;
  }

  function toast(text, kind = "", ms = 4200) {
    const t = el("div", `toast ${kind}`, text);
    ui.toasts.append(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, ms);
  }

  function greet() {
    const h = new Date().getHours();
    const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
    const name = status.user || "";
    ui.greeting.textContent = name ? `${part}, ${name}` : part;
    ui.emptyTitle.textContent = name ? `${part}, ${name}. How can I help?` : "How can I help?";
  }

  // ---------------------------------------------------------------- messages
  function hideEmpty() { ui.empty.hidden = true; }

  function addUser(text, source) {
    hideEmpty();
    const row = el("div", "msg user");
    const body = el("div", "body");
    if (source === "voice") body.append(el("span", "via", "🎙 voice"));
    body.append(document.createTextNode(text));
    row.append(body);
    ui.messages.append(row);
    scrollDown(true);
  }

  function addJarvis(turnId, { pending = true, text = "" } = {}) {
    hideEmpty();
    const row = el("div", `msg jarvis${pending ? " pending" : ""}`);
    const avatar = el("div", "avatar");
    const content = el("div", "content");
    const who = el("div", "who", "JARVIS");
    const tools = el("div", "tools");
    tools.hidden = true;
    const body = el("div", "text");
    if (pending) body.innerHTML = '<span class="thinking-dots"><i></i><i></i><i></i></span>';
    else body.innerHTML = markdown(text);
    content.append(who, tools, body);
    row.append(avatar, content);
    ui.messages.append(row);
    const turn = { root: row, body, tools, content, raw: "", frame: 0 };
    if (turnId) turns.set(turnId, turn);
    scrollDown(true);
    return turn;
  }

  function renderStreaming(turn) {
    if (turn.frame) return;
    turn.frame = requestAnimationFrame(() => {
      turn.frame = 0;
      const stick = nearBottom();
      turn.body.innerHTML = markdown(turn.raw);
      const last = turn.body.lastElementChild || turn.body;
      last.classList.add("caret");
      if (stick) scrollDown(true);
    });
  }

  function finishTurn(turn, msg) {
    if (turn.frame) cancelAnimationFrame(turn.frame);
    turn.frame = 0;
    turn.root.classList.remove("pending");
    if (msg.error) turn.root.classList.add("error");
    turn.body.innerHTML = markdown(msg.text || "");
    const meta = el("div", "meta");
    meta.append(el("span", "", timeStr()));
    if (msg.ms != null) meta.append(el("span", "", `${(msg.ms / 1000).toFixed(1)}s`));
    if (msg.model) meta.append(el("span", "", msg.model));
    const copy = el("button", "", "copy");
    copy.type = "button";
    copy.addEventListener("click", () => copyText(msg.text || "", copy));
    meta.append(copy);
    turn.content.append(meta);
    scrollDown();
  }

  function copyText(text, btn) {
    navigator.clipboard?.writeText(text).then(() => {
      const old = btn.textContent;
      btn.textContent = "copied";
      setTimeout(() => (btn.textContent = old), 1200);
    });
  }

  ui.messages.addEventListener("click", (e) => {
    const btn = e.target.closest("pre .copy");
    if (btn) copyText(btn.nextElementSibling.textContent, btn);
  });

  function addToolChip(turn, name, statusName) {
    turn.tools.hidden = false;
    let chip = turn.tools.querySelector(`[data-tool="${CSS.escape(name)}"]:not(.done):not(.declined)`);
    if (!chip) {
      chip = el("span", "tool", prettyTool(name));
      chip.dataset.tool = name;
      turn.tools.append(chip);
    }
    if (statusName === "done") chip.classList.add("done");
    if (statusName === "declined") chip.classList.add("declined");
  }

  function logActivity(name, statusName) {
    if (statusName === "running") return;
    const first = ui.activity.querySelector(".muted");
    if (first) first.remove();
    const li = el("li", statusName);
    li.append(el("time", "", timeStr()), el("b", "", prettyTool(name)), el("span", "muted", statusName === "done" ? "completed" : statusName));
    ui.activity.prepend(li);
    while (ui.activity.children.length > 40) ui.activity.lastChild.remove();
  }

  function showHeard(text) {
    const line = el("div", "heard", text);
    ui.messages.append(line);
    scrollDown();
    setTimeout(() => line.remove(), 6000);
  }

  // ---------------------------------------------------------------- state + status
  const STATE_LABEL = {
    idle: "Online", thinking: "Thinking", listening: "Listening", speaking: "Speaking",
    sleeping: `Waiting for wake word`, offline: "Offline",
  };

  function setState(s) {
    state = s;
    document.body.dataset.state = s;
    ui.stateLabel.textContent = s === "sleeping" ? `Say “${cap(status.wake_word || "Jarvis")}”` : STATE_LABEL[s] || s;
    ui.mic.classList.toggle("live", s === "listening" && !status.handsfree);
    ui.stop.hidden = s !== "speaking";
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

  function applyStatus(s) {
    status = s;
    ui.version.textContent = `v${s.version || "2"}`;
    greet();

    ui.voice.checked = !!s.voice_replies;
    ui.voice.disabled = !s.tts;
    ui.handsfree.checked = !!s.handsfree;
    ui.handsfree.disabled = !(s.tts && s.mic);
    ui.hfHint.textContent = s.mic ? `Say “${cap(s.wake_word || "jarvis")}…” any time` : "No microphone found";
    ui.mic.disabled = !s.mic || s.handsfree;
    ui.mic.title = !s.mic ? "No microphone found" : s.handsfree ? "Hands-free is listening" : "Speak";

    ui.model.replaceChildren(...(s.models || [s.model]).map((m) => {
      const o = el("option", "", m);
      o.value = m;
      o.selected = m === s.model;
      return o;
    }));

    ui.keys.replaceChildren(...(s.keys || []).map((line) => {
      const kind = /: active$/.test(line) ? "ok" : /: ready$/.test(line) ? "" : /retry in/.test(line) ? "wait" : "bad";
      return el("li", kind, line.replace(/^key /, "#"));
    }));
    if (!(s.keys || []).length) ui.keys.append(el("li", "", "no keys"));

    ui.skillsCount.textContent = (s.skills || []).length;
    ui.skills.replaceChildren(...(s.skills || []).map((sk) => {
      const li = el("li");
      li.append(el("b", "", sk.name), el("p", "", sk.description));
      const tl = el("div", "tl");
      sk.tools.forEach((t) => tl.append(el("span", "", t.replace(/_/g, " "))));
      li.append(tl);
      return li;
    }));
    if (s.state) setState(s.state);
  }

  // ---------------------------------------------------------------- memory panel
  const trashIcon = '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></svg>';

  async function loadMemory() {
    try {
      const r = await fetch("/api/memory");
      const { facts, notes } = await r.json();
      ui.facts.replaceChildren(...facts.map((f) => memItem(f.key.replace(/_/g, " "), f.value, null, () => del(`/api/facts/${encodeURIComponent(f.key)}`))));
      if (!facts.length) ui.facts.append(el("li", "muted", "Nothing yet — tell me about yourself."));
      ui.notes.replaceChildren(...notes.map((n) => memItem(null, n.content, n.created_at, () => del(`/api/notes/${n.id}`))));
      if (!notes.length) ui.notes.append(el("li", "muted", "No notes. Try “remember to…”"));
    } catch { /* offline: keep what is shown */ }
  }
  function memItem(key, value, date, onDelete) {
    const li = el("li");
    if (key) li.append(el("span", "k", key));
    li.append(el("span", "v", value));
    if (date) li.append(el("span", "d", new Date(date).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })));
    const b = el("button", "del");
    b.type = "button";
    b.title = "Forget this";
    b.setAttribute("aria-label", "Delete");
    b.innerHTML = trashIcon;
    b.addEventListener("click", onDelete);
    li.append(b);
    return li;
  }
  async function del(url) {
    await fetch(url, { method: "DELETE" });
    loadMemory();
  }
  let memTimer = 0;
  const refreshMemorySoon = () => { clearTimeout(memTimer); memTimer = setTimeout(loadMemory, 400); };

  // ---------------------------------------------------------------- vitals + clock
  async function loadVitals() {
    if (document.hidden) return;
    try {
      const v = await (await fetch("/api/vitals")).json();
      meter("cpu", v.cpu);
      meter("ram", v.ram);
      if (v.battery != null) { $("#bat-row").hidden = false; meter("bat", v.battery, v.plugged ? "⚡" : ""); }
    } catch { /* ignore */ }
  }
  function meter(id, val, suffix = "") {
    const bar = $(`#${id}-bar`);
    bar.style.width = `${Math.max(2, val)}%`;
    bar.classList.toggle("hot", id !== "bat" ? val > 85 : val < 20);
    $(`#${id}-val`).textContent = `${Math.round(val)}%${suffix}`;
  }
  function tickClock() { $("#clock").textContent = timeStr(); }

  // ---------------------------------------------------------------- history
  async function loadHistory() {
    if (historyLoaded) return;
    historyLoaded = true;
    try {
      const items = await (await fetch("/api/history")).json();
      for (const m of items) {
        if (m.role === "user") addUser(m.text);
        else addJarvis(null, { pending: false, text: m.text });
      }
      scrollDown(true);
    } catch { /* ignore */ }
  }

  // ---------------------------------------------------------------- websocket
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ui.conn.className = "conn";
    ui.conn.lastElementChild.textContent = retry ? "Reconnecting…" : "Connecting…";

    ws.onopen = () => {
      retry = 0;
      ui.conn.className = "conn on";
      ui.conn.lastElementChild.textContent = "Connected";
      loadHistory();
      loadMemory();
    };
    ws.onclose = () => {
      ui.conn.className = "conn off";
      ui.conn.lastElementChild.textContent = "Offline — retrying";
      setState("offline");
      const delay = Math.min(8000, 500 * 2 ** retry++);
      setTimeout(connect, delay);
    };
    ws.onmessage = (e) => handle(JSON.parse(e.data));
  }

  function send(obj) {
    if (ws && ws.readyState === WebSocket.OPEN) { ws.send(JSON.stringify(obj)); return true; }
    toast("Not connected to Jarvis yet.", "error");
    return false;
  }

  function handle(msg) {
    switch (msg.type) {
      case "status": applyStatus(msg); break;
      case "state": setState(msg.state); break;
      case "user":
        addUser(msg.text, msg.source);
        addJarvis(msg.turn);
        break;
      case "token": {
        const turn = turns.get(msg.turn);
        if (!turn) break;
        turn.raw += msg.text;
        renderStreaming(turn);
        break;
      }
      case "tool": {
        const turn = turns.get(msg.turn);
        if (turn) addToolChip(turn, msg.name, msg.status);
        logActivity(msg.name, msg.status);
        break;
      }
      case "done": {
        const turn = turns.get(msg.turn) || addJarvis(msg.turn);
        finishTurn(turn, msg);
        turns.delete(msg.turn);
        refreshMemorySoon();
        break;
      }
      case "heard":
        if (msg.ignored) showHeard(`heard “${msg.text}” — no wake word`);
        else if (!msg.text) toast("Didn't catch that — try again a little closer to the mic.");
        break;
      case "notice": showHeard(`Jarvis: ${msg.text}`); break;
      case "error": toast(msg.text, "error", 6000); break;
      case "confirm": openConfirm(msg); break;
      case "confirm_closed":
        if (pendingConfirm === msg.id && ui.dialog.open) { pendingConfirm = null; ui.dialog.close("timeout"); }
        break;
      case "cleared":
        ui.messages.querySelectorAll(".msg, .heard").forEach((n) => n.remove());
        turns.clear();
        ui.empty.hidden = false;
        break;
    }
  }

  // ---------------------------------------------------------------- confirm dialog
  function openConfirm(msg) {
    pendingConfirm = msg.id;
    $("#confirm-name").textContent = prettyTool(msg.name);
    $("#confirm-args").textContent = JSON.stringify(msg.args, null, 2);
    if (!ui.dialog.open) ui.dialog.showModal();
  }
  ui.dialog.addEventListener("close", () => {
    if (pendingConfirm) send({ type: "confirm", id: pendingConfirm, ok: ui.dialog.returnValue === "yes" });
    pendingConfirm = null;
  });

  // ---------------------------------------------------------------- composer
  function autosize() {
    ui.input.style.height = "auto";
    ui.input.style.height = `${Math.min(ui.input.scrollHeight, 200)}px`;
    ui.send.disabled = !ui.input.value.trim();
  }
  ui.input.addEventListener("input", autosize);
  ui.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      ui.form.requestSubmit();
    }
  });
  ui.form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = ui.input.value.trim();
    if (!text) return;
    if (send({ type: "chat", text })) {
      ui.input.value = "";
      autosize();
    }
  });

  $("#suggestions").addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (chip) send({ type: "chat", text: chip.dataset.q });
  });
  ui.mic.addEventListener("click", () => send({ type: "listen" }));
  ui.stop.addEventListener("click", () => send({ type: "stop_speaking" }));
  ui.voice.addEventListener("change", () => send({ type: "voice", on: ui.voice.checked }));
  ui.handsfree.addEventListener("change", () => {
    send({ type: "handsfree", on: ui.handsfree.checked });
    toast(ui.handsfree.checked ? `Hands-free on — say “${cap(status.wake_word || "jarvis")}, …”` : "Hands-free off");
  });
  ui.model.addEventListener("change", () => {
    send({ type: "model", name: ui.model.value });
    toast(`Switched to ${ui.model.value}`);
  });
  $("#clear-btn").addEventListener("click", () => send({ type: "clear" }));

  // ---------------------------------------------------------------- drawers + tabs + keys
  function openDrawer(side) {
    closeDrawers();
    (side === "left" ? ui.left : ui.right).classList.add("open");
    ui.scrim.hidden = false;
  }
  function closeDrawers() {
    ui.left.classList.remove("open");
    ui.right.classList.remove("open");
    ui.scrim.hidden = true;
  }
  $("#open-left").addEventListener("click", () => openDrawer("left"));
  $("#open-right").addEventListener("click", () => openDrawer("right"));
  ui.scrim.addEventListener("click", closeDrawers);

  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => { t.classList.toggle("active", t === tab); t.setAttribute("aria-selected", t === tab); });
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === tab.dataset.tab));
    if (tab.dataset.tab === "memory") loadMemory();
  }));

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeDrawers();
      if (state === "speaking") send({ type: "stop_speaking" });
    } else if (e.key === "/" && document.activeElement !== ui.input && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      e.preventDefault();
      ui.input.focus();
    }
  });

  // ---------------------------------------------------------------- boot
  greet();
  tickClock();
  setInterval(tickClock, 10_000);
  loadVitals();
  setInterval(loadVitals, 3000);
  document.addEventListener("visibilitychange", loadVitals);
  setState("offline");
  connect();
  ui.input.focus();
})();

/* Settee TV, the TV page: views, a focus moved by arrow keys or the phone, channel numbers, clock, weather, news, photos.
   Everything from outside (news, settings) is set with textContent, never as HTML. */
(function () {
  "use strict";

  var STRINGS = {
    en: { brand: "Settee", home: "Home", channels: "Channels", news: "News", weather: "Weather", photos: "Photos",
          phone: "Phone remote", topStory: "Top story", noPhotos: "Your photos show here",
          channelsHint: "Press a number on the remote to open a channel.", phoneTitle: "Use your phone as the remote",
          step1: "Join the same Wi-Fi as this TV.", step2: "Scan the code with the phone's camera.", step3: "Or open", step3b: "and type",
          morning: "Good morning", afternoon: "Good afternoon", evening: "Good evening", night: "Good night",
          noChannels: "No channels yet. Add them on this PC at http://127.0.0.1:{port}/settings",
          noNews: "No news right now.", newsOff: "News is turned off in the settings.", newsFrom: "From {host}",
          noWeather: "The weather has not arrived yet.", noPlace: "Choose your town on this PC at http://127.0.0.1:{port}/settings", rain: "{p}% rain", today: "Today",
          photosEmpty: "Put photos in {folder} and they show here.", photoOf: "{n} of {total}",
          phones: { 0: "No phone is paired yet.", 1: "1 phone is paired.", n: "{n} phones are paired." },
          opening: "Opening {name}", noSuch: "There is no channel {n}", notOpened: "Could not open it: {why}",
          offline: "The TV lost its server. Trying again…", channel: "Channel",
          wx: { 0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 51: "Drizzle", 61: "Rain", 66: "Freezing rain",
                71: "Snow", 77: "Snow grains", 80: "Showers", 85: "Snow showers", 95: "Thunder" } },
    sv: { brand: "Settee", home: "Hem", channels: "Kanaler", news: "Nyheter", weather: "Väder", photos: "Foton",
          phone: "Mobilen som fjärr", topStory: "Toppnyhet", noPhotos: "Dina foton visas här",
          channelsHint: "Tryck en siffra på fjärren för att öppna en kanal.", phoneTitle: "Använd mobilen som fjärrkontroll",
          step1: "Anslut till samma wifi som TV:n.", step2: "Skanna koden med mobilens kamera.", step3: "Eller öppna", step3b: "och skriv",
          morning: "God morgon", afternoon: "God eftermiddag", evening: "God kväll", night: "God natt",
          noChannels: "Inga kanaler än. Lägg till dem på den här datorn på http://127.0.0.1:{port}/settings",
          noNews: "Inga nyheter just nu.", newsOff: "Nyheterna är avstängda i inställningarna.", newsFrom: "Från {host}",
          noWeather: "Vädret har inte kommit än.", noPlace: "Välj din ort på den här datorn på http://127.0.0.1:{port}/settings", rain: "{p} % regn", today: "I dag",
          photosEmpty: "Lägg foton i {folder} så visas de här.", photoOf: "{n} av {total}",
          phones: { 0: "Ingen mobil är kopplad än.", 1: "1 mobil är kopplad.", n: "{n} mobiler är kopplade." },
          opening: "Öppnar {name}", noSuch: "Det finns ingen kanal {n}", notOpened: "Kunde inte öppna: {why}",
          offline: "TV:n tappade servern. Försöker igen…", channel: "Kanal",
          wx: { 0: "Klart", 1: "Mest klart", 2: "Halvklart", 3: "Mulet", 45: "Dimma", 51: "Duggregn", 61: "Regn", 66: "Underkylt regn",
                71: "Snö", 77: "Snökorn", 80: "Skurar", 85: "Snöbyar", 95: "Åska" } }
  };
  var SWATCHES = [["#c8553d", "#fff"], ["#e0ad4c", "#1d1606"], ["#6f9452", "#fff"], ["#2f8a8a", "#fff"],
                  ["#4472ad", "#fff"], ["#8d71b3", "#fff"], ["#c86d8c", "#fff"], ["#61788a", "#fff"]];

  var $ = function (id) { return document.getElementById(id); };
  var state = null, lang = "en", T = STRINGS.en, view = "home", focused = null, lastCmd = 0;
  var photoCount = 0, photoIndex = -1, slideIndex = 0, newsItems = [];

  function fill(text, vars) {
    return String(text).replace(/\{(\w+)\}/g, function (m, k) { return vars && k in vars ? vars[k] : m; });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function api(path, body) {
    var opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    return fetch(path, opts).then(function (r) {
      return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || r.status); return d; });
    });
  }
  var toastTimer = 0;
  function toast(text) {
    var t = $("toast");
    t.textContent = text;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 3500);
  }

  /* ---------------------------------------------------------------- settings and language */
  function applyState(s) {
    var before = JSON.stringify(state);
    state = s;
    if (JSON.stringify(s) === before) return;
    var set = s.settings;
    document.documentElement.dataset.look = set.look;
    document.documentElement.dataset.accent = set.accent;
    lang = STRINGS[set.language] ? set.language : "en";
    T = STRINGS[lang];
    document.documentElement.lang = lang;
    Array.prototype.forEach.call(document.querySelectorAll("[data-t]"), function (n) {
      if (T[n.dataset.t]) n.textContent = T[n.dataset.t];
    });
    renderChannels();
    renderPairing();
    tick();
  }
  function loadState() {
    return api("/api/state").then(function (s) {
      if (!state) lastCmd = s.last;
      applyState(s);
    });
  }

  /* ---------------------------------------------------------------- channels */
  function initials(name) {
    var words = name.replace(/[^\p{L}\p{N} ]/gu, " ").trim().split(/\s+/);
    var s = words.length > 1 ? words[0][0] + words[1][0] : (words[0] || "?").slice(0, 2);
    return s.toUpperCase();
  }
  function chanEl(c, i) {
    var b = el("button", "card chan focusable");
    b.setAttribute("role", "listitem");
    b.dataset.n = i + 1;
    var sw = SWATCHES[i % SWATCHES.length];
    var s = el("span", "swatch", initials(c.name));
    s.style.setProperty("--sw", sw[0]);
    s.style.setProperty("--sw-ink", sw[1]);
    var text = el("span", "chan-text");
    text.appendChild(el("span", "chan-name", c.name));
    var num = el("span", "chan-num", T.channel + " ");
    num.appendChild(el("b", "", String(i + 1)));
    text.appendChild(num);
    b.appendChild(s);
    b.appendChild(text);
    return b;
  }
  function renderChannels() {
    var list = state.settings.channels, strip = $("strip"), grid = $("grid");
    strip.textContent = "";
    grid.textContent = "";
    if (!list.length) {
      grid.appendChild(el("p", "empty-note", fill(T.noChannels, { port: location.port || 80 })));
      return;
    }
    list.slice(0, 5).forEach(function (c, i) { strip.appendChild(chanEl(c, i)); });
    list.forEach(function (c, i) { grid.appendChild(chanEl(c, i)); });
  }

  /* ---------------------------------------------------------------- number entry: the plate fills, then the channel opens */
  var typed = "", typeTimer = 0;
  function digit(d) {
    typed = (typed + d).slice(-2);
    var n = parseInt(typed, 10), c = state.settings.channels[n - 1];
    $("osd").hidden = false;
    $("osd-num").textContent = typed;
    $("osd-name").textContent = c ? c.name : fill(T.noSuch, { n: n });
    var fillBar = $("osd-fill");
    fillBar.classList.remove("run");
    void fillBar.offsetWidth;
    if (c) fillBar.classList.add("run");
    clearTimeout(typeTimer);
    var soon = c && (typed.length === 2 || n * 10 > state.settings.channels.length);
    typeTimer = setTimeout(function () {
      $("osd").hidden = true;
      typed = "";
      if (c) openChannel(n);
    }, soon ? 1600 : 2200);
  }
  function openChannel(n) {
    var c = state.settings.channels[n - 1];
    if (!c) return toast(fill(T.noSuch, { n: n }));
    toast(fill(T.opening, { name: c.name }));
    api("/api/open", { n: n }).catch(function (e) { toast(fill(T.notOpened, { why: e.message })); });
  }

  /* ---------------------------------------------------------------- clock */
  function tick() {
    var now = new Date(), loc = lang === "sv" ? "sv-SE" : "en-GB";
    var hh = String(now.getHours()).padStart(2, "0"), mm = String(now.getMinutes()).padStart(2, "0");
    var clock = $("clock");
    clock.querySelector(".hh").textContent = hh;
    clock.querySelector(".mm").textContent = mm;
    var date = new Intl.DateTimeFormat(loc, { weekday: "long", day: "numeric", month: "long" }).format(now);
    $("date").textContent = date.charAt(0).toUpperCase() + date.slice(1);
    var h = now.getHours();
    $("greet").textContent = h < 5 ? T.night : h < 12 ? T.morning : h < 18 ? T.afternoon : h < 23 ? T.evening : T.night;
    $("rail-time").textContent = hh + ":" + mm;
  }

  /* ---------------------------------------------------------------- weather and news */
  function wxKey(code) {
    var keys = [95, 85, 80, 77, 71, 66, 61, 51, 45, 3, 2, 1, 0];
    for (var i = 0; i < keys.length; i++) if (code >= keys[i]) return keys[i];
    return 0;
  }
  function wxIcon(code, day) {
    var k = wxKey(code);
    if (k === 0 || k === 1) return day === false ? "w-moon" : "w-sun";
    return { 2: "w-partly", 3: "w-cloud", 45: "w-fog", 51: "w-rain", 61: "w-rain", 66: "w-rain", 80: "w-rain",
             71: "w-snow", 77: "w-snow", 85: "w-snow", 95: "w-storm" }[k] || "w-cloud";
  }
  function useIcon(svg, id) { svg.querySelector("use").setAttribute("href", "#" + id); }
  function deg(v) { return v == null ? "--" : Math.round(v) + "°"; }
  function renderWeather(w) {
    var place = state.settings.place ? state.settings.place.name : "";
    $("wx-place").textContent = place;
    $("wx-title-place").textContent = place;
    var days = $("days");
    days.textContent = "";
    if (!w) {
      var why = place ? T.noWeather : fill(T.noPlace, { port: location.port || 80 });
      $("wx-text").textContent = why;
      $("wx-now-line").textContent = why;
      return;
    }
    $("wx-temp").textContent = deg(w.now.temp);
    $("wx-text").textContent = T.wx[wxKey(w.now.code)];
    useIcon($("wx-icon"), wxIcon(w.now.code, w.now.day));
    var d0 = w.days[0];
    $("wx-range").textContent = d0 ? deg(d0.high) + " / " + deg(d0.low) + (d0.rain != null ? " · " + fill(T.rain, { p: d0.rain }) : "") : "";
    $("wx-now-line").textContent = deg(w.now.temp) + " · " + T.wx[wxKey(w.now.code)];
    var loc = lang === "sv" ? "sv-SE" : "en-GB";
    w.days.forEach(function (d, i) {
      var li = el("li", "card day");
      var date = new Date(d.date + "T12:00:00");
      var name = i === 0 ? T.today : new Intl.DateTimeFormat(loc, { weekday: "long" }).format(date);
      li.appendChild(el("span", "day-name", name.charAt(0).toUpperCase() + name.slice(1)));
      li.appendChild(el("span", "day-date", new Intl.DateTimeFormat(loc, { day: "numeric", month: "short" }).format(date)));
      var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      var use = document.createElementNS("http://www.w3.org/2000/svg", "use");
      use.setAttribute("href", "#" + wxIcon(d.code, true));
      svg.appendChild(use);
      li.appendChild(svg);
      li.appendChild(el("span", "day-text", T.wx[wxKey(d.code)]));
      var temps = el("span", "day-temps", deg(d.high) + " ");
      temps.appendChild(el("span", "low", deg(d.low)));
      li.appendChild(temps);
      li.appendChild(el("span", "day-rain", d.rain != null ? fill(T.rain, { p: d.rain }) : ""));
      days.appendChild(li);
    });
  }
  function ago(iso) {
    var t = Date.parse(iso);
    if (!t) return "";
    var min = Math.max(1, Math.round((Date.now() - t) / 60000));
    var rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
    return min < 60 ? rtf.format(-min, "minute") : min < 1440 ? rtf.format(-Math.round(min / 60), "hour") : rtf.format(-Math.round(min / 1440), "day");
  }
  function renderNews(items) {
    newsItems = items || [];
    var feed = state.settings.news, list = $("stories");
    list.textContent = "";
    var host = "";
    try { host = feed ? new URL(feed).hostname.replace(/^www\.|^feeds\./, "") : ""; } catch (e) { host = ""; }
    $("news-source").textContent = host ? fill(T.newsFrom, { host: host }) : "";
    var top = newsItems[0];
    $("headline").textContent = top ? top.title : (feed ? T.noNews : T.newsOff);
    $("headline-when").textContent = top ? ago(top.when) : "";
    if (!newsItems.length) {
      list.appendChild(el("li", "empty-note", feed ? T.noNews : T.newsOff));
      return;
    }
    newsItems.slice(0, 8).forEach(function (n) {
      var li = el("li");
      var b = el("button", "card story focusable");
      b.appendChild(el("span", "story-title", n.title));
      if (n.summary) b.appendChild(el("span", "story-sum", n.summary));
      b.appendChild(el("span", "story-when", ago(n.when)));
      li.appendChild(b);
      list.appendChild(li);
    });
  }
  function loadFeeds() {
    return api("/api/feeds").then(function (f) { renderWeather(f.weather); renderNews(f.news); })
      .catch(function () { renderWeather(null); });
  }

  /* ---------------------------------------------------------------- photos: a slow cross-fade */
  function showPhoto(a, b, index) {
    var next = a.classList.contains("on") ? b : a, prev = next === a ? b : a;
    var img = new Image();
    img.onload = function () {
      next.style.backgroundImage = "url('/photo/" + index + "')";
      next.classList.add("on");
      prev.classList.remove("on");
    };
    img.src = "/photo/" + index;
  }
  function loadPhotos() {
    return api("/api/photos").then(function (p) {
      photoCount = p.count;
      $("photo-empty").hidden = photoCount > 0;
      $("slide-empty").textContent = photoCount ? "" : fill(T.photosEmpty, { folder: p.folder });
      if (photoCount && photoIndex < 0) nextHomePhoto();
    });
  }
  function nextHomePhoto() {
    if (!photoCount) return;
    photoIndex = (photoIndex + 1) % photoCount;
    showPhoto($("photo-a"), $("photo-b"), photoIndex);
  }
  function slide(step) {
    if (!photoCount) return;
    slideIndex = (slideIndex + step + photoCount) % photoCount;
    showPhoto($("slide-a"), $("slide-b"), slideIndex);
    $("slide-count").textContent = fill(T.photoOf, { n: slideIndex + 1, total: photoCount });
  }

  /* ---------------------------------------------------------------- the phone remote */
  function renderPairing() {
    var p = state.pairing;
    $("pair-url").textContent = p.url.split("#")[0];
    $("pair-code").textContent = p.code.replace(/(\d{3})(\d{3})/, "$1 $2");
    $("pair-phones").textContent = fill(p.phones === 0 ? T.phones[0] : p.phones === 1 ? T.phones[1] : T.phones.n, { n: p.phones });
    if (window.qrcode) {
      var q = window.qrcode(0, "M");
      q.addData(p.url);
      q.make();
      $("qr").innerHTML = q.createSvgTag({ cellSize: 4, margin: 0, scalable: true });  // markup from the QR library, never from data
    }
  }

  /* ---------------------------------------------------------------- views and focus */
  function show(name, keepFocus) {
    view = name;
    Array.prototype.forEach.call(document.querySelectorAll(".view"), function (v) { v.hidden = v.id !== "view-" + name; });
    Array.prototype.forEach.call(document.querySelectorAll(".go"), function (g) {
      g.classList.toggle("current", g.dataset.view === name);
      if (g.dataset.view === name) g.setAttribute("aria-current", "page"); else g.removeAttribute("aria-current");
    });
    if (name === "photos") slide(0);
    if (!keepFocus) focus(document.querySelector('.go[data-view="' + name + '"]'));
  }
  function candidates() {
    var list = Array.prototype.slice.call(document.querySelectorAll(".go"));
    var v = $("view-" + view);
    return list.concat(Array.prototype.slice.call(v.querySelectorAll(".focusable")));
  }
  function focus(node) {
    if (!node) return;
    if (focused) focused.classList.remove("focus");
    focused = node;
    node.classList.add("focus");
    node.focus({ preventScroll: true });
  }
  function move(dir) {
    if (view === "photos" && (dir === "left" || dir === "right") && !focused.classList.contains("go")) return slide(dir === "left" ? -1 : 1);
    if (!focused) return focus(candidates()[0]);
    var r = focused.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2, best = null, bestScore = Infinity;
    candidates().forEach(function (c) {
      if (c === focused) return;
      var q = c.getBoundingClientRect();
      if (!q.width) return;
      var x = q.left + q.width / 2, y = q.top + q.height / 2, dx = x - cx, dy = y - cy;
      var ahead = dir === "left" ? -dx : dir === "right" ? dx : dir === "up" ? -dy : dy;
      var side = dir === "left" || dir === "right" ? Math.abs(dy) : Math.abs(dx);
      if (ahead <= 4) return;
      var score = ahead + side * 2.2;
      if (score < bestScore) { bestScore = score; best = c; }
    });
    if (best) {
      focus(best);
      if (best.classList.contains("go")) show(best.dataset.view, true);
    } else if (dir === "right" && view === "photos") {
      slide(1);
    }
  }
  function ok() {
    if (!focused) return;
    if (focused.classList.contains("go")) {
      show(focused.dataset.view, true);
      var first = $("view-" + view).querySelector(".focusable");
      if (first) focus(first);
    } else if (focused.dataset.go) {
      show(focused.dataset.go);
    } else if (focused.dataset.n) {
      openChannel(parseInt(focused.dataset.n, 10));
    }
  }
  function back() {
    if (!focused || !focused.classList.contains("go")) return focus(document.querySelector('.go[data-view="' + view + '"]'));
    if (view !== "home") show("home");
  }
  function command(cmd) {
    if (cmd.indexOf("digit:") === 0) return digit(cmd.slice(6));
    if (cmd === "ok") return ok();
    if (cmd === "back") return back();
    if (cmd === "home") return show("home");
    move(cmd);
  }

  document.addEventListener("keydown", function (e) {
    var keys = { ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right", Enter: "ok", " ": "ok",
                 Escape: "back", Backspace: "back", BrowserBack: "back", Home: "home", h: "home" };
    if (/^[0-9]$/.test(e.key)) { e.preventDefault(); return digit(e.key); }
    if (keys[e.key]) { e.preventDefault(); command(keys[e.key]); }
  });
  document.addEventListener("mousemove", function () { document.body.classList.add("pointer"); });
  document.addEventListener("click", function (e) {
    var t = e.target.closest(".go, .focusable");
    if (!t) return;
    focus(t);
    ok();
  });

  /* the phone's key presses arrive by long poll */
  function poll() {
    fetch("/api/commands?after=" + lastCmd).then(function (r) { return r.json(); }).then(function (d) {
      if (d.last < lastCmd) lastCmd = 0;  // the server restarted
      d.commands.forEach(function (c) { if (c.id > lastCmd) command(c.cmd); });
      lastCmd = Math.max(lastCmd, d.last);
      poll();
    }).catch(function () {
      toast(T.offline);
      setTimeout(poll, 3000);
    });
  }

  loadState().then(function () {
    show("home");
    loadFeeds();
    loadPhotos();
    poll();
  }).catch(function () { toast(T.offline); setTimeout(function () { location.reload(); }, 5000); });
  setInterval(tick, 1000);
  setInterval(function () { loadState().catch(function () {}); }, 15000);
  setInterval(loadFeeds, 10 * 60 * 1000);
  setInterval(function () { loadPhotos(); }, 5 * 60 * 1000);
  setInterval(function () { if (view === "home") nextHomePhoto(); else if (view === "photos") slide(1); }, 12000);
})();

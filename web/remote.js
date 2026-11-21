/* Settee TV, the phone remote: pair with the code from the TV, then send key presses. */
(function () {
  "use strict";
  var STRINGS = {
    en: { pairTitle: "Connect to the TV", pairLead: "Type the six digits shown on the TV under Phone remote.", codeLabel: "Code from the TV",
          connect: "Connect", back: "Back", numbers: "Numbers", channels: "Channels", wrong: "That code is not the one on the TV. Try again.",
          locked: "Too many wrong codes. Wait a minute, then try again.", lost: "The TV does not answer. Is it on, and is the phone on the same Wi-Fi?",
          again: "The TV forgot this phone. Type the new code from the TV.", sent: "", opening: "Channel {n}" },
    sv: { pairTitle: "Koppla till TV:n", pairLead: "Skriv de sex siffrorna som TV:n visar under Mobilen som fjärr.", codeLabel: "Koden från TV:n",
          connect: "Koppla", back: "Tillbaka", numbers: "Siffror", channels: "Kanaler", wrong: "Det är inte koden som TV:n visar. Försök igen.",
          locked: "För många fel koder. Vänta en minut och försök igen.", lost: "TV:n svarar inte. Är den på, och är mobilen på samma wifi?",
          again: "TV:n har glömt den här mobilen. Skriv den nya koden från TV:n.", sent: "", opening: "Kanal {n}" }
  };
  var $ = function (id) { return document.getElementById(id); };
  var T = STRINGS[(navigator.language || "en").slice(0, 2)] || STRINGS.en;

  function translate() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-t]"), function (n) { if (T[n.dataset.t]) n.textContent = T[n.dataset.t]; });
  }
  function post(path, body) {
    return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), credentials: "same-origin" });
  }
  function status(text) { $("status").textContent = text || ""; }

  function showPair(message) {
    $("remote").hidden = true;
    $("pair").hidden = false;
    $("pair-error").textContent = message || "";
    var fromQr = (location.hash || "").replace(/\D/g, "").slice(0, 6);
    if (fromQr.length === 6 && !message) {
      $("code").value = fromQr;
      pair(fromQr);
    } else {
      $("code").focus();
    }
  }
  function pair(code) {
    var button = document.querySelector("#pair-form .primary");
    button.disabled = true;
    post("/api/pair", { code: code }).then(function (r) {
      button.disabled = false;
      if (r.ok) { history.replaceState(null, "", "/remote"); return start(); }
      $("pair-error").textContent = r.status === 429 ? T.locked : T.wrong;
      $("code").select();
    }).catch(function () { button.disabled = false; $("pair-error").textContent = T.lost; });
  }
  $("pair-form").addEventListener("submit", function (e) {
    e.preventDefault();
    pair($("code").value.replace(/\D/g, ""));
  });
  $("code").addEventListener("input", function () {
    var d = this.value.replace(/\D/g, "").slice(0, 6);
    this.value = d.length > 3 ? d.slice(0, 3) + " " + d.slice(3) : d;
    if (d.length === 6) pair(d);
  });

  function send(cmd, button) {
    if (navigator.vibrate) navigator.vibrate(12);
    if (button) { button.classList.remove("pressed"); void button.offsetWidth; button.classList.add("pressed"); }
    return post("/api/remote", { cmd: cmd }).then(function (r) {
      if (r.status === 403) return showPair(T.again);
      status(r.ok ? "" : T.lost);
    }).catch(function () { status(T.lost); });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-cmd]");
    if (b) send(b.dataset.cmd, b);
  });
  $("toggle-keys").addEventListener("click", function () {
    var open = $("keys").hidden;
    $("keys").hidden = !open;
    this.setAttribute("aria-expanded", String(open));
  });
  [1, 2, 3, 4, 5, 6, 7, 8, 9, 0].forEach(function (n) {
    var b = document.createElement("button");
    b.className = "key" + (n === 0 ? " zero" : "");
    b.textContent = String(n);
    b.dataset.cmd = "digit:" + n;
    $("keys").appendChild(b);
  });

  function start() {
    return fetch("/api/remote/state", { credentials: "same-origin" }).then(function (r) {
      if (r.status === 403) return showPair();
      return r.json().then(function (s) {
        document.documentElement.dataset.look = s.look;
        document.documentElement.dataset.accent = s.accent;
        T = STRINGS[s.language] || T;
        translate();
        var list = $("chans");
        list.textContent = "";
        s.channels.forEach(function (c) {
          var li = document.createElement("li");
          var b = document.createElement("button");
          b.className = "chan";
          var n = document.createElement("span");
          n.className = "chan-n";
          n.textContent = String(c.n);
          var name = document.createElement("span");
          name.className = "chan-name";
          name.textContent = c.name;
          b.appendChild(n);
          b.appendChild(name);
          b.addEventListener("click", function () {
            String(c.n).split("").reduce(function (p, d) { return p.then(function () { return send("digit:" + d); }); }, Promise.resolve());
          });
          li.appendChild(b);
          list.appendChild(li);
        });
        $("pair").hidden = true;
        $("remote").hidden = false;
      });
    }).catch(function () { showPair(T.lost); });
  }
  translate();
  start();
})();

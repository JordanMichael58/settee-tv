/* Settee TV settings: read /api/state, edit, POST /api/settings (the server cleans every field again). */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var form = $("form"), place = null;

  function api(path, body) {
    var opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    return fetch(path, opts).then(function (r) {
      return r.json().then(function (d) { if (!r.ok) throw new Error(d.error || r.status); return d; });
    });
  }
  function renumber() {
    Array.prototype.forEach.call($("channels").children, function (li, i) { li.querySelector(".num").textContent = String(i + 1); });
  }
  function addRow(c) {
    var li = $("row").content.firstElementChild.cloneNode(true);
    li.querySelector(".c-name").value = c ? c.name : "";
    li.querySelector(".c-kind").value = c ? c.kind : "web";
    li.querySelector(".c-target").value = c ? c.target : "";
    li.querySelector(".c-up").addEventListener("click", function () {
      if (li.previousElementSibling) li.parentNode.insertBefore(li, li.previousElementSibling);
      renumber();
    });
    li.querySelector(".c-del").addEventListener("click", function () { li.remove(); renumber(); });
    $("channels").appendChild(li);
    renumber();
    return li;
  }
  function showPlace() { $("place-now").textContent = place ? place.name : "not chosen"; }
  function fill(s) {
    form.look.value = s.settings.look;
    form.accent.value = s.settings.accent;
    form.language.value = s.settings.language;
    form.news.value = s.settings.news;
    form.photos.value = s.settings.photos;
    place = s.settings.place;
    showPlace();
    $("channels").textContent = "";
    s.settings.channels.forEach(addRow);
    var n = s.pairing.phones;
    $("phones").textContent = n === 0 ? "No phone is paired." : n === 1 ? "1 phone is paired." : n + " phones are paired.";
  }

  $("add").addEventListener("click", function () { addRow(null).querySelector(".c-name").focus(); });
  $("place-find").addEventListener("click", function () {
    var q = $("place-q").value.trim(), hits = $("hits");
    if (!q) return;
    hits.textContent = "";
    api("/api/geocode?q=" + encodeURIComponent(q)).then(function (list) {
      if (!list.length) {
        var none = document.createElement("li");
        none.textContent = "Nothing found. Try the nearest bigger town.";
        hits.appendChild(none);
      }
      list.forEach(function (p) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button";
        b.textContent = p.name;
        b.addEventListener("click", function () { place = { name: p.short, lat: p.lat, lon: p.lon }; showPlace(); hits.textContent = ""; });
        li.appendChild(b);
        hits.appendChild(li);
      });
    }).catch(function (e) { $("saved").textContent = e.message; });
  });
  $("place-q").addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); $("place-find").click(); } });
  $("forget").addEventListener("click", function () {
    api("/api/forget", {}).then(function () { $("phones").textContent = "No phone is paired. Pair again from the TV."; });
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var channels = Array.prototype.map.call($("channels").children, function (li) {
      return { name: li.querySelector(".c-name").value, kind: li.querySelector(".c-kind").value, target: li.querySelector(".c-target").value };
    });
    api("/api/settings", { look: form.look.value, accent: form.accent.value, language: form.language.value, news: form.news.value,
                           photos: form.photos.value, place: place, channels: channels })
      .then(function (saved) {
        var dropped = channels.length - saved.channels.length;
        $("saved").textContent = "Saved." + (dropped > 0 ? " " + dropped + " channel(s) were left out: a web site needs an address starting with http:// or https://." : "");
        $("channels").textContent = "";
        saved.channels.forEach(addRow);
      })
      .catch(function (err) { $("saved").textContent = "Not saved: " + err.message; });
  });
  api("/api/state").then(fill).catch(function () { $("saved").textContent = "The Settee TV server does not answer."; });
})();

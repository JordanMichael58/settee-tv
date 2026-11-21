"""The outside world: the weather (Open-Meteo, no key), one news feed (RSS or Atom) and place search for the settings
page. Answers are cached; a failed fetch keeps the last good answer, so the TV never goes blank."""
import json
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_TTL, NEWS_TTL = 15 * 60, 10 * 60
AGENT = "SetteeTV/1.0 (+https://github.com/JordanMichael58/settee-tv)"
MAX_BYTES = 2 * 1024 * 1024


def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(MAX_BYTES)


def weather_url(lat, lon):
    return WEATHER_URL + "?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 5,
        "current": "temperature_2m,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"})


def parse_weather(body):
    """Open-Meteo JSON -> {"now": {temp, code, day}, "days": [{date, code, high, low, rain}]}."""
    d = json.loads(body)
    cur, daily = d.get("current") or {}, d.get("daily") or {}
    days = []
    for i, day in enumerate(daily.get("time") or []):
        def col(name):
            v = (daily.get(name) or [None] * (i + 1))
            return v[i] if i < len(v) else None
        days.append({"date": day, "code": col("weather_code"), "high": col("temperature_2m_max"),
                     "low": col("temperature_2m_min"), "rain": col("precipitation_probability_max")})
    return {"now": {"temp": cur.get("temperature_2m"), "code": cur.get("weather_code"), "day": cur.get("is_day", 1) == 1},
            "days": days[:5]}


TAG_RE = re.compile(r"<[^>]+>")


def _plain(text, limit):
    text = TAG_RE.sub(" ", text or "")
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&lt;", "<"), ("&gt;", ">")):
        text = text.replace(a, b)
    return " ".join(text.split())[:limit]


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_news(body, limit=12):
    """RSS 2.0 or Atom -> [{title, summary, when}] (when: ISO time or "")."""
    if re.search(rb"<!(DOCTYPE|ENTITY)", body if isinstance(body, bytes) else body.encode("utf-8"), re.I):
        raise ValueError("a feed with a DTD")  # entity expansion (billion laughs) on Python 3.8's expat; feeds need none
    root = ET.fromstring(body)
    items = []
    for el in root.iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        fields = {_local(c.tag): (c.text or "") for c in el}
        title = _plain(fields.get("title"), 200)
        if not title:
            continue
        when = ""
        raw = fields.get("pubDate") or fields.get("published") or fields.get("updated") or ""
        try:
            when = parsedate_to_datetime(raw).isoformat() if fields.get("pubDate") else raw.strip()
        except (TypeError, ValueError, IndexError):
            when = ""
        items.append({"title": title, "summary": _plain(fields.get("description") or fields.get("summary"), 400), "when": when})
        if len(items) >= limit:
            break
    return items


def geocode(name, fetch=fetch):
    """A place name -> up to five {name, lat, lon} for the settings page."""
    body = fetch(GEOCODE_URL + "?" + urllib.parse.urlencode({"name": name[:80], "count": 5, "format": "json"}))
    out = []
    for r in json.loads(body).get("results") or []:
        label = ", ".join(p for p in (r.get("name"), r.get("admin1"), r.get("country")) if p)
        out.append({"name": label, "short": r.get("name") or label, "lat": r.get("latitude"), "lon": r.get("longitude")})
    return out


class Feeds:
    """Cached weather and news for the current settings; fetch is swappable in tests."""

    def __init__(self, fetch=fetch, clock=time.time):
        self.fetch, self.clock = fetch, clock
        self._cache = {}
        self._lock = threading.Lock()

    def _get(self, key, ttl, load):
        with self._lock:
            hit = self._cache.get(key)
        if hit and self.clock() - hit[0] < ttl:
            return hit[1]
        try:
            value = load()
        except Exception as e:  # network, JSON or XML: keep what we had
            print("[feeds] %s failed: %s" % (key[0], type(e).__name__), flush=True)
            return hit[1] if hit else None
        with self._lock:
            self._cache[key] = (self.clock(), value)
        return value

    def weather(self, place):
        return self._get(("weather", place["lat"], place["lon"]), WEATHER_TTL,
                         lambda: parse_weather(self.fetch(weather_url(place["lat"], place["lon"]))))

    def news(self, url):
        if not url:
            return []
        return self._get(("news", url), NEWS_TTL, lambda: parse_news(self.fetch(url)))

"""Settee TV: settings cleaning, pairing, the feeds' parsers and the HTTP gates, against a real server on a free port
with a recording launcher and a stand-in internet. Runs on Python 3.8+."""
import ast
import http.client
import json
import tempfile
import unittest
from pathlib import Path

from settee import config, feeds, remote, server
from settee.launcher import FakeLauncher

ROOT = Path(__file__).resolve().parent.parent

WEATHER = json.dumps({"current": {"temperature_2m": 4.6, "weather_code": 61, "is_day": 1},
                      "daily": {"time": ["2026-11-21", "2026-11-22"], "weather_code": [61, 3], "temperature_2m_max": [6.1, 5.0],
                                "temperature_2m_min": [1.2, -0.4], "precipitation_probability_max": [80, 10]}}).encode()
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Bridge &amp; tunnel reopen</title><description>&lt;p&gt;Traffic is back.&lt;/p&gt;</description>
<pubDate>Sat, 21 Nov 2026 08:00:00 GMT</pubDate></item><item><title></title></item>
<item><title>Second story</title></item></channel></rss>"""
ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Atom one</title><summary>s</summary>
<updated>2026-11-21T08:00:00Z</updated></entry></feed>"""


class Settings(unittest.TestCase):
    def test_bad_values_fall_back_and_bad_channels_are_dropped(self):
        s = config.clean({"look": "neon", "accent": "plum", "language": "sv", "place": {"name": "Lund", "lat": "55.7", "lon": 13.19},
                          "channels": [{"name": "A", "kind": "web", "target": "javascript:alert(1)"},
                                       {"name": "B", "kind": "app", "target": "C:\\vlc.exe"}, {"name": "", "kind": "web", "target": "https://x"},
                                       "junk", {"name": "C", "kind": "web", "target": "https://c.example/"}]})
        self.assertEqual((s["look"], s["accent"], s["language"]), ("evening", "plum", "sv"))
        self.assertEqual(s["place"], {"name": "Lund", "lat": 55.7, "lon": 13.19})
        self.assertEqual([c["name"] for c in s["channels"]], ["B", "C"])
        self.assertEqual(s["news"], config.FEEDS["sv"])

    def test_no_home_town_by_default_and_a_broken_file_still_loads(self):
        folder = Path(tempfile.mkdtemp())
        (folder / "config.json").write_text("{not json", encoding="utf-8")
        s = config.Settings(folder).load()
        self.assertIsNone(s["place"])
        self.assertEqual(len(s["channels"]), len(config.DEFAULT_CHANNELS))

    def test_empty_news_turns_it_off_and_save_round_trips(self):
        st = config.Settings(Path(tempfile.mkdtemp()))
        saved = st.save({"news": "", "channels": [{"name": "N" * 99, "kind": "web", "target": "http://n"}] * 40})
        self.assertEqual(saved["news"], "")
        self.assertEqual(len(saved["channels"]), config.MAX_CHANNELS)
        self.assertEqual(len(saved["channels"][0]["name"]), 40)
        self.assertEqual(st.load(), saved)


class Pairing(unittest.TestCase):
    def setUp(self):
        self.now = [0.0]
        self.path = Path(tempfile.mkdtemp()) / "paired.json"
        self.p = remote.Pairing(self.path, clock=lambda: self.now[0])

    def test_the_right_code_gives_a_token_kept_only_as_a_hash_and_a_new_code(self):
        code = self.p.code
        token = self.p.pair(code)
        self.assertTrue(self.p.valid(token))
        self.assertNotEqual(self.p.code, code)
        self.assertNotIn(token, self.path.read_text())
        self.assertTrue(remote.Pairing(self.path).valid(token))
        self.assertFalse(self.p.valid("") or self.p.valid("guess"))

    def test_five_wrong_codes_lock_it_for_a_minute(self):
        for _ in range(remote.MAX_WRONG):
            self.assertIsNone(self.p.pair("nope"))
        with self.assertRaises(remote.LockedOut):
            self.p.pair(self.p.code)
        self.now[0] += remote.LOCK_SECONDS + 1
        self.assertTrue(self.p.pair(self.p.code))

    def test_only_the_last_eight_phones_and_forget_all(self):
        tokens = [self.p.pair(self.p.code) for _ in range(remote.MAX_PHONES + 1)]
        self.assertFalse(self.p.valid(tokens[0]))
        self.assertTrue(self.p.valid(tokens[-1]))
        self.p.forget_all()
        self.assertEqual(self.p.phones, 0)

    def test_who_counts_as_home(self):
        for ip, home in (("192.168.1.20", True), ("10.0.0.5", True), ("127.0.0.1", True), ("::1", True),
                         ("::ffff:192.168.1.5", True), ("8.8.8.8", False), ("169.254.1.1", False), ("nonsense", False)):
            self.assertEqual(remote.is_private(ip), home, ip)
        self.assertTrue(remote.is_local("127.0.0.1"))
        self.assertFalse(remote.is_local("192.168.1.2"))


class Feeds(unittest.TestCase):
    def test_weather(self):
        w = feeds.parse_weather(WEATHER)
        self.assertEqual(w["now"], {"temp": 4.6, "code": 61, "day": True})
        self.assertEqual(w["days"][1], {"date": "2026-11-22", "code": 3, "high": 5.0, "low": -0.4, "rain": 10})

    def test_rss_and_atom_as_plain_text(self):
        items = feeds.parse_news(RSS)
        self.assertEqual([i["title"] for i in items], ["Bridge & tunnel reopen", "Second story"])
        self.assertEqual(items[0]["summary"], "Traffic is back.")
        self.assertTrue(items[0]["when"].startswith("2026-11-21T08:00"))
        self.assertEqual(feeds.parse_news(ATOM)[0]["title"], "Atom one")

    def test_a_feed_with_entities_is_refused(self):
        bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><item><title>&a;</title></item></channel></rss>'
        with self.assertRaises(ValueError):
            feeds.parse_news(bomb)

    def test_a_failed_fetch_keeps_the_last_good_answer(self):
        answers = [RSS]
        f = feeds.Feeds(fetch=lambda url: answers.pop(0), clock=lambda: clock[0])
        clock = [0.0]
        self.assertEqual(len(f.news("https://n")), 2)
        clock[0] += feeds.NEWS_TTL + 1
        self.assertEqual(len(f.news("https://n")), 2)  # the stand-in has nothing left: an IndexError, the cache answers
        self.assertEqual(f.news(""), [])


def internet(url):
    if url.startswith(feeds.WEATHER_URL):
        return WEATHER
    if url.startswith(feeds.GEOCODE_URL):
        return json.dumps({"results": [{"name": "Lund", "admin1": "Skåne", "country": "Sweden", "latitude": 55.7, "longitude": 13.19}]}).encode()
    return RSS


class Http(unittest.TestCase):
    def setUp(self):
        self.data = Path(tempfile.mkdtemp())
        self.launcher = FakeLauncher()
        self.app = server.App(self.data, self.launcher, 0, fetch=internet)
        self.httpd = server.make_server(self.app, "127.0.0.1")
        import threading
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.host = "127.0.0.1:%d" % self.app.port

    def ask(self, method, path, body=None, headers=None, ip=None):
        h = {"Host": self.host}
        if body is not None:
            h.update({"Content-Type": "application/json", "Origin": "http://" + self.host})
        h.update(headers or {})
        original = server.Handler.ip
        if ip:  # what a phone or a stranger on another address would get
            server.Handler.ip = property(lambda s: ip)
        try:
            c = http.client.HTTPConnection(self.host, timeout=10)
            c.request(method, path, json.dumps(body) if body is not None else None, h)
            r = c.getresponse()
            data = r.read()
            c.close()
        finally:
            server.Handler.ip = original
        try:
            return r.status, json.loads(data), r
        except ValueError:
            return r.status, data, r

    def test_the_tv_page_and_its_data_are_for_this_pc_only(self):
        status, body, r = self.ask("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("default-src 'self'", r.getheader("Content-Security-Policy"))
        self.assertEqual(self.ask("GET", "/api/state", ip="192.168.1.20")[0], 403)
        self.assertEqual(self.ask("GET", "/settings", ip="192.168.1.20")[0], 403)
        self.assertEqual(self.ask("GET", "/remote", ip="192.168.1.20")[0], 200)
        self.assertEqual(self.ask("GET", "/remote", ip="8.8.8.8")[0], 403)

    def test_a_site_renamed_to_point_here_is_refused(self):
        self.assertEqual(self.ask("GET", "/api/state", headers={"Host": "evil.example:%d" % self.app.port})[0], 403)

    def test_posts_need_the_matching_origin_and_json(self):
        self.assertEqual(self.ask("POST", "/api/open", {"n": 1}, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.ask("POST", "/api/open", {"n": 1}, headers={"Content-Type": "text/plain"})[0], 400)

    def test_a_phone_pairs_then_sends_keys_the_tv_reads(self):
        phone = "192.168.1.20"
        self.assertEqual(self.ask("POST", "/api/remote", {"cmd": "up"}, ip=phone)[0], 403)
        self.assertEqual(self.ask("POST", "/api/pair", {"code": "000000" if self.app.pairing.code != "000000" else "111111"}, ip=phone)[0], 403)
        status, _, r = self.ask("POST", "/api/pair", {"code": self.app.pairing.code}, ip=phone)
        self.assertEqual(status, 200)
        cookie = r.getheader("Set-Cookie").split(";")[0]
        self.assertIn("HttpOnly", r.getheader("Set-Cookie"))
        self.assertEqual(self.ask("POST", "/api/remote", {"cmd": "launch-rockets"}, {"Cookie": cookie}, ip=phone)[0], 400)
        for cmd in ("down", "digit:2", "home"):
            self.assertEqual(self.ask("POST", "/api/remote", {"cmd": cmd}, {"Cookie": cookie}, ip=phone)[0], 200)
        self.assertEqual(self.launcher.calls, [("show",)])  # Home brings the TV to the front
        self.assertEqual(self.ask("GET", "/api/remote/state", headers={"Cookie": cookie}, ip=phone)[1]["channels"][0],
                         {"n": 1, "name": "YouTube"})
        got = self.ask("GET", "/api/commands?after=0")[1]
        self.assertEqual([c["cmd"] for c in got["commands"]], ["down", "digit:2", "home"])

    def test_home_reopens_a_closed_tv_window(self):
        self.launcher.show_tv = lambda: False  # someone closed the TV window
        status, _, r = self.ask("POST", "/api/pair", {"code": self.app.pairing.code}, ip="192.168.1.20")
        cookie = r.getheader("Set-Cookie").split(";")[0]
        self.assertEqual(self.ask("POST", "/api/remote", {"cmd": "home"}, {"Cookie": cookie}, ip="192.168.1.20")[0], 200)
        self.assertEqual(self.launcher.calls, [("start", "http://127.0.0.1:%d/" % self.app.port)])

    def test_channels_open_by_number_from_the_tv_only(self):
        self.assertEqual(self.ask("POST", "/api/open", {"n": 2})[1], {"opened": "Netflix"})
        self.assertEqual(self.ask("POST", "/api/open", {"n": 99})[0], 404)
        self.assertEqual(self.ask("POST", "/api/open", {"n": 1}, ip="192.168.1.20")[0], 403)
        self.assertEqual(self.launcher.calls, [("open", "Netflix")])

    def test_settings_feeds_and_place_search(self):
        self.assertIsNone(self.ask("GET", "/api/feeds")[1]["weather"])  # no town chosen yet
        hits = self.ask("GET", "/api/geocode?q=Lund")[1]
        self.assertEqual(hits[0]["name"], "Lund, Skåne, Sweden")
        saved = self.ask("POST", "/api/settings", {"place": {"name": "Lund", "lat": 55.7, "lon": 13.19}, "look": "daylight"})[1]
        self.assertEqual(saved["look"], "daylight")
        f = self.ask("GET", "/api/feeds")[1]
        self.assertEqual(f["weather"]["now"]["temp"], 4.6)
        self.assertEqual(f["news"][0]["title"], "Bridge & tunnel reopen")

    def test_photos_only_from_the_folder_and_static_never_leaves_web(self):
        photos = self.data / "pics"
        photos.mkdir()
        (photos / "a.png").write_bytes(b"\x89PNG")
        (photos / "notes.txt").write_text("x")
        self.ask("POST", "/api/settings", {"photos": str(photos)})
        self.assertEqual(self.ask("GET", "/api/photos")[1]["count"], 1)
        self.assertEqual(self.ask("GET", "/photo/0")[0], 200)
        self.assertEqual(self.ask("GET", "/photo/1")[0], 404)
        self.assertEqual(self.ask("GET", "/static/../settee/server.py")[0], 404)
        self.assertEqual(self.ask("GET", "/static/tv.css")[0], 200)


class LanAddress(unittest.TestCase):
    def test_home_wifi_beats_a_vpn_route(self):
        self.assertEqual(server.pick_lan("172.24.0.2", ["172.24.0.2", "192.168.1.20"]), "192.168.1.20")
        self.assertEqual(server.pick_lan("10.0.0.5", ["10.0.0.5"]), "10.0.0.5")
        self.assertEqual(server.pick_lan("192.168.1.4", ["192.168.9.9", "192.168.1.4"]), "192.168.1.4")


class OldPython(unittest.TestCase):
    def test_every_file_is_python_3_8(self):  # the last Python for Windows 7
        for path in list((ROOT / "settee").glob("*.py")) + list((ROOT / "tests").glob("*.py")):
            ast.parse(path.read_text(encoding="utf-8"), str(path), feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main()

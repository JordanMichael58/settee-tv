"""The HTTP server: the TV page and its data for this PC only, the remote page for the home network, and the remote's
commands for paired phones only. Every POST needs a JSON body and an Origin matching the Host; every page answers
only under an IP address or localhost (a web site renamed to point here is refused)."""
import ipaddress
import json
import mimetypes
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import feeds as feeds_mod
from .config import Settings
from .remote import LockedOut, Pairing, is_local, is_private

WEB = Path(__file__).resolve().parent.parent / "web"
COMMANDS = {"up", "down", "left", "right", "ok", "back", "home"} | {"digit:%d" % i for i in range(10)}
PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PHOTOS, MAX_BODY, POLL_SECONDS = 500, 64 * 1024, 25
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".svg": "image/svg+xml", ".json": "application/json", ".png": "image/png", ".ico": "image/x-icon"}


def pick_lan(routed, addresses):
    """A home Wi-Fi address (192.168.x) beats the default route, which a VPN adapter often owns."""
    home = [a for a in addresses if a.startswith("192.168.")]
    return routed if routed.startswith("192.168.") or not home else home[0]


def lan_ip():
    """This PC's address on the home network (no packet leaves: UDP connect only picks the route)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        routed = s.getsockname()[0]
    except OSError:
        routed = "127.0.0.1"
    finally:
        s.close()
    try:
        addresses = [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        addresses = []
    return pick_lan(routed, addresses)


class Commands:
    """The remote's key presses, read by the TV page with a long poll."""

    def __init__(self):
        self.items, self.last = [], 0
        self.cond = threading.Condition()

    def push(self, cmd):
        with self.cond:
            self.last += 1
            self.items = (self.items + [{"id": self.last, "cmd": cmd}])[-50:]
            self.cond.notify_all()

    def after(self, n, wait=POLL_SECONDS):
        end = time.monotonic() + wait
        with self.cond:
            while self.last <= n and time.monotonic() < end:
                self.cond.wait(end - time.monotonic())
            return {"last": self.last, "commands": [c for c in self.items if c["id"] > n]}


class Photos:
    def __init__(self):
        self._cache = (0.0, "", [])

    def list(self, folder):
        at, was, files = self._cache
        if was == folder and time.monotonic() - at < 60:
            return files
        root, found = Path(folder), []
        try:
            for p in sorted(root.iterdir()) if root.is_dir() else []:
                if p.is_dir():
                    found += [q for q in sorted(p.iterdir()) if q.suffix.lower() in PHOTO_TYPES and q.is_file()]
                elif p.suffix.lower() in PHOTO_TYPES:
                    found.append(p)
                if len(found) >= MAX_PHOTOS:
                    break
        except OSError:
            pass
        files = found[:MAX_PHOTOS]
        self._cache = (time.monotonic(), folder, files)
        return files


class App:
    def __init__(self, data, launcher, port, fetch=feeds_mod.fetch):
        self.data = Path(data)
        self.settings = Settings(self.data)
        self.pairing = Pairing(self.data / "paired.json")
        self.feeds = feeds_mod.Feeds(fetch)
        self.launcher, self.port, self.fetch = launcher, port, fetch
        self.commands, self.photos = Commands(), Photos()

    def remote_url(self):
        return "http://%s:%d/remote#%s" % (lan_ip(), self.port, self.pairing.code)


def host_ok(host):
    name = urllib.parse.urlsplit("//" + (host or "")).hostname or ""
    if name == "localhost":
        return True
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "SetteeTV"
    app = None  # set by make_server

    def log_message(self, fmt, *args):
        pass

    # ---------------------------------------------------------------- answers
    def send(self, code, body=b"", ctype="application/json", headers=()):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy", CSP)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def fail(self, code, why):
        self.send(code, {"error": why})

    def file(self, path):
        try:
            body = path.read_bytes()
        except OSError:
            return self.fail(404, "not found")
        ctype = TYPES.get(path.suffix.lower()) or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send(200, body, ctype)

    # ---------------------------------------------------------------- who is asking
    @property
    def ip(self):
        return self.client_address[0]

    def local(self):
        return is_local(self.ip)

    def token(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "settee":
                return v
        return ""

    def paired(self):
        return self.local() or self.app.pairing.valid(self.token())

    def origin_ok(self):
        return self.headers.get("Origin") == "http://" + (self.headers.get("Host") or "")

    def body(self):
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return None
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return None
            data = json.loads(self.rfile.read(n) or b"{}")
            return data if isinstance(data, dict) else None
        except ValueError:
            return None

    # ---------------------------------------------------------------- GET
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not host_ok(self.headers.get("Host")) or not is_private(self.ip):
            return self.fail(403, "not from here")
        url = urllib.parse.urlsplit(self.path)
        path, query = url.path, urllib.parse.parse_qs(url.query)
        app = self.app
        if path == "/remote":
            return self.file(WEB / "remote.html")
        if path.startswith("/static/"):
            name = path[len("/static/"):]
            target = (WEB / name).resolve()
            if WEB not in target.parents or not target.is_file() or target.suffix == ".html":
                return self.fail(404, "not found")
            return self.file(target)
        if path == "/api/remote/state":
            if not self.paired():
                return self.fail(403, "pair first")
            s = app.settings.load()
            return self.send(200, {"language": s["language"], "look": s["look"], "accent": s["accent"],
                                   "channels": [{"n": i + 1, "name": c["name"]} for i, c in enumerate(s["channels"])]})
        if not self.local():
            return self.fail(403, "only on the TV")
        if path in ("/", "/tv"):
            return self.file(WEB / "tv.html")
        if path == "/settings":
            return self.file(WEB / "settings.html")
        if path == "/api/state":
            return self.send(200, {"settings": app.settings.load(), "pairing": {
                "code": app.pairing.code, "url": app.remote_url(), "phones": app.pairing.phones},
                                   "last": app.commands.last})
        if path == "/api/feeds":
            s = app.settings.load()
            return self.send(200, {"weather": app.feeds.weather(s["place"]) if s["place"] else None,
                                   "news": app.feeds.news(s["news"])})
        if path == "/api/photos":
            s = app.settings.load()
            return self.send(200, {"count": len(app.photos.list(s["photos"])), "folder": s["photos"]})
        if path.startswith("/photo/"):
            files = app.photos.list(app.settings.load()["photos"])
            try:
                return self.file(files[int(path[len("/photo/"):])])
            except (ValueError, IndexError):
                return self.fail(404, "no such photo")
        if path == "/api/commands":
            try:
                after = int((query.get("after") or ["0"])[0])
            except ValueError:
                after = 0
            return self.send(200, app.commands.after(after))
        if path == "/api/geocode":
            q = (query.get("q") or [""])[0].strip()
            if not q:
                return self.send(200, [])
            try:
                return self.send(200, feeds_mod.geocode(q, app.fetch))
            except Exception as e:
                return self.fail(502, "the place search did not answer (%s)" % type(e).__name__)
        return self.fail(404, "not found")

    # ---------------------------------------------------------------- POST
    def do_POST(self):
        if not host_ok(self.headers.get("Host")) or not is_private(self.ip):
            return self.fail(403, "not from here")
        if not self.origin_ok():
            return self.fail(403, "wrong origin")
        data = self.body()
        if data is None:
            return self.fail(400, "send JSON")
        app, path = self.app, urllib.parse.urlsplit(self.path).path
        if path == "/api/pair":
            try:
                token = app.pairing.pair(str(data.get("code", "")).strip())
            except LockedOut:
                return self.fail(429, "too many wrong codes, wait a minute")
            if not token:
                return self.fail(403, "wrong code")
            return self.send(200, {"paired": True}, headers=[(
                "Set-Cookie", "settee=%s; Path=/; Max-Age=31536000; HttpOnly; SameSite=Strict" % token)])
        if path == "/api/remote":
            if not self.paired():
                return self.fail(403, "pair first")
            cmd = data.get("cmd")
            if cmd not in COMMANDS:
                return self.fail(400, "unknown key")
            if cmd == "home" and not app.launcher.show_tv():  # the TV window was closed: open it again
                app.launcher.start_tv("http://127.0.0.1:%d/" % app.port)
            app.commands.push(cmd)
            return self.send(200, {"ok": True})
        if not self.local():
            return self.fail(403, "only on the TV")
        if path == "/api/open":
            channels = app.settings.load()["channels"]
            n = data.get("n")
            if not isinstance(n, int) or not 1 <= n <= len(channels):
                return self.fail(404, "no channel %s" % n)
            try:
                app.launcher.open_channel(channels[n - 1])
            except OSError as e:
                return self.fail(500, "could not open %s (%s)" % (channels[n - 1]["name"], e.strerror or type(e).__name__))
            return self.send(200, {"opened": channels[n - 1]["name"]})
        if path == "/api/show":
            return self.send(200, {"shown": app.launcher.show_tv()})
        if path == "/api/settings":
            return self.send(200, app.settings.save(data))
        if path == "/api/forget":
            app.pairing.forget_all()
            return self.send(200, {"phones": 0})
        return self.fail(404, "not found")


def make_server(app, host="0.0.0.0"):
    handler = type("BoundHandler", (Handler,), {"app": app})
    httpd = ThreadingHTTPServer((host, app.port), handler)
    httpd.daemon_threads = True
    app.port = httpd.server_address[1]  # port 0 (tests) gets a free one
    return httpd

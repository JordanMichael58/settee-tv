"""Phone pairing: the TV shows a six-digit code (and a QR code holding it); a phone that sends it gets a random token
kept as a cookie. Only token hashes are saved. Five wrong codes in a row lock pairing for a minute."""
import hashlib
import ipaddress
import json
import secrets
import threading
import time
from pathlib import Path

MAX_PHONES = 8
MAX_WRONG, LOCK_SECONDS = 5, 60


class LockedOut(Exception):
    pass


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_code():
    return "%06d" % secrets.randbelow(1000000)


class Pairing:
    def __init__(self, path, clock=time.monotonic):
        self.path, self.clock = Path(path), clock
        self.code = new_code()
        self._wrong, self._locked_until = 0, 0.0
        self._lock = threading.Lock()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._hashes = [h for h in data.get("tokens", []) if isinstance(h, str)][-MAX_PHONES:]
        except (OSError, ValueError, AttributeError):
            self._hashes = []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"tokens": self._hashes}), encoding="utf-8")

    def pair(self, code):
        """The right code -> a new token (and a fresh code for the next phone); a wrong one -> None."""
        with self._lock:
            if self.clock() < self._locked_until:
                raise LockedOut()
            if not isinstance(code, str) or not secrets.compare_digest(code.encode("utf-8"), self.code.encode("utf-8")):
                self._wrong += 1
                if self._wrong >= MAX_WRONG:
                    self._wrong, self._locked_until = 0, self.clock() + LOCK_SECONDS
                return None
            self._wrong = 0
            token = secrets.token_urlsafe(32)
            self._hashes = (self._hashes + [_hash(token)])[-MAX_PHONES:]
            self._save()
            self.code = new_code()
            return token

    def valid(self, token):
        return bool(token) and _hash(token) in self._hashes

    def forget_all(self):
        with self._lock:
            self._hashes = []
            self._save()
            self.code = new_code()

    @property
    def phones(self):
        return len(self._hashes)


def is_local(ip):
    try:
        return ipaddress.ip_address(ip.split("%")[0]).is_loopback
    except ValueError:
        return False


def is_private(ip):
    """The home network (or this PC): what may open the remote page."""
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    return a.is_loopback or (a.is_private and not a.is_link_local and not a.is_unspecified)

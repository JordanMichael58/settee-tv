"""python -m settee: starts the server and the TV window.
--demo: no real PC actions (channels and Home are only recorded), this PC only, data in ./.demo."""
import argparse
import os
import sys
import threading
from pathlib import Path

from . import __version__
from .launcher import FakeLauncher, Launcher
from .server import App, make_server


def default_data():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return str(Path(base) / "SetteeTV" / "data")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="settee", description="Settee TV " + __version__)
    ap.add_argument("--port", type=int, default=4960)
    ap.add_argument("--data", default=None, help=r"settings folder (default %%LOCALAPPDATA%%\SetteeTV\data)")
    ap.add_argument("--no-kiosk", action="store_true", help="open the TV page in a normal window")
    ap.add_argument("--no-browser", action="store_true", help="start only the server")
    ap.add_argument("--demo", action="store_true", help="try it out: nothing is opened on the PC")
    a = ap.parse_args(argv)
    data = a.data or (str(Path(".demo")) if a.demo else default_data())
    launcher = FakeLauncher() if a.demo else Launcher(data)
    app = App(data, launcher, a.port)
    try:
        httpd = make_server(app, "127.0.0.1" if a.demo else "0.0.0.0")
    except OSError as e:
        print("Settee TV could not use port %d (%s). Is it already running?" % (a.port, e), file=sys.stderr)
        return 1
    url = "http://127.0.0.1:%d/" % app.port
    print("Settee TV %s on %s  (phone: %s)" % (__version__, url, app.remote_url()), flush=True)
    if not a.no_browser:
        threading.Timer(0.5, Launcher(data).start_tv, (url,), {"kiosk": not (a.no_kiosk or a.demo)}).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

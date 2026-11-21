"""What Settee TV does to the PC: open a channel (a web site in the browser or a program), bring the TV window back
to the front, and start the TV page itself full screen. FakeLauncher records instead, for tests and --demo."""
import ctypes
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

TITLE = "Settee TV"


def browsers():
    """Chrome and Edge in their usual places (per-user first), the ones that have a kiosk mode."""
    roots = [os.environ.get(k) for k in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)")]
    rel = [r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe"]
    return [str(Path(root) / r) for r in rel for root in roots if root and (Path(root) / r).is_file()]


class Launcher:
    def __init__(self, data_folder):
        self.data = Path(data_folder)

    def open_channel(self, channel):
        target = channel["target"]
        if channel["kind"] == "web":
            if sys.platform == "win32":
                os.startfile(target)  # the person's own default browser, signed in as they are
            else:
                webbrowser.open(target)
        elif sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen([target])

    def show_tv(self):
        """Brings the TV window to the front (Windows): the remote's Home key while a channel is open."""
        if sys.platform != "win32":
            return False
        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def each(hwnd, _):
            n = user32.GetWindowTextLengthW(hwnd)
            if n and user32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.startswith(TITLE):
                    found.append(hwnd)
                    return False
            return True
        user32.EnumWindows(each, 0)
        if not found:
            return False
        user32.keybd_event(0x12, 0, 0, 0)  # a tap of Alt: Windows only lets the foreground app hand over focus
        user32.keybd_event(0x12, 0, 2, 0)
        user32.ShowWindow(found[0], 9)  # SW_RESTORE
        return bool(user32.SetForegroundWindow(found[0]))

    def start_tv(self, url, kiosk=True):
        """Chrome or Edge full screen on its own profile (so it is the TV's window), else the default browser."""
        found = browsers()
        if found and kiosk:
            profile = self.data / "browser"
            subprocess.Popen([found[0], "--kiosk", "--app=" + url, "--user-data-dir=" + str(profile),
                              "--no-first-run", "--disable-session-crashed-bubble", "--autoplay-policy=no-user-gesture-required"])
        else:
            webbrowser.open(url)


class FakeLauncher:
    def __init__(self, *_):
        self.calls = []

    def open_channel(self, channel):
        self.calls.append(("open", channel["name"]))

    def show_tv(self):
        self.calls.append(("show",))
        return True

    def start_tv(self, url, kiosk=True):
        self.calls.append(("start", url))

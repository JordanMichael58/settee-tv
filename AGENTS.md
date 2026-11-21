# Setting up Settee TV (for AI coding agents)

You are setting up Settee TV on the Windows PC that is connected to the person's television. Follow these steps in order
and tell the person what you did after each one.

## Rules

- Do not use admin rights, and do not change firewall, antivirus, Smart App Control or any other security setting. If
  Windows asks whether Python can use the network, the **person** answers it: they should allow private networks only.
- Do not install anything except what `install.ps1` installs: the official Python 3.8.10 embeddable zip from python.org,
  and only when no Python 3.8 or newer is present.
- Ask before you create or change anything outside `%LOCALAPPDATA%\SetteeTV`, the Desktop shortcut and the Startup shortcut.
- Never type passwords. Channels open web sites in the person's normal browser, where they sign in themselves.

## Steps

1. Get the code: `git clone https://github.com/JordanMichael58/settee-tv` (or download and unzip the ZIP).
2. Check it: `python -m unittest discover -s tests` (or `py -3 -m unittest discover -s tests`) should end with `OK`.
   Skip this step if the PC has no Python yet. The installer brings its own.
3. Preview the install: `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -DryRun`, and show the person the steps it prints.
4. Install: run `install.bat` (or the same command as step 3 without `-DryRun`). The TV opens full screen.
5. Ask the person for their town, news feed (RSS), photo folder and channels. Set them on the settings page
   `http://127.0.0.1:4960/settings` on this PC, or POST the whole settings object as JSON to
   `http://127.0.0.1:4960/api/settings` with the header `Origin: http://127.0.0.1:4960`.
   - Read the current settings with `GET http://127.0.0.1:4960/api/state`.
   - Find a town's coordinates with `GET /api/geocode?q=<town>`.
   - A channel is `{"name": "...", "kind": "web", "target": "https://..."}` or `{"name": "...", "kind": "app", "target": "C:\\path\\to\\program.exe"}`.
6. Tell the person to open **Phone remote** on the TV and scan the QR code with their phone.

## Facts you may need

- Program: `%LOCALAPPDATA%\SetteeTV\app`. Settings and phone pairings: `%LOCALAPPDATA%\SetteeTV\data`. Port: 4960.
- Start by hand: `pythonw -m settee` in the program folder. Use `--no-kiosk` for a normal window, or `--demo` to try it with nothing launched.
- Remove: `uninstall.bat`. The settings folder stays.
- The code must keep running on Python 3.8 (Windows 7), so use no newer syntax. A test checks this.

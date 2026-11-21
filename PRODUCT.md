# Product

Settee TV: a fullscreen TV home screen for a Windows PC connected to a television, run from the sofa with a phone as
the remote. Open source (MIT), for anyone who turns an old PC into a living-room TV.

Lines marked *(assumed)* are design assumptions, not research findings.

## Platform
web

## Stack
Python 3.8+ standard library only (the last Python for Windows 7), static HTML/CSS/JS with no build step, no external
fonts or CDNs. The TV page runs in Chrome or Edge in kiosk mode; the remote page in any phone browser on the same Wi-Fi.

## Users
People watching TV from a sofa about three metres away, often older or not technical *(assumed)*; whoever installs it
is a relative with a little more PC knowledge.

## Product Purpose
Open the family's channels (web sites or programs on the PC) by name or by number, and glance at the time, the weather,
the news and family photos, without a keyboard or mouse.

## Positioning
A menu down the left side, a home screen of cards, warm
"Evening" and "Daylight" looks with five accent colours, no brand logos (coloured initials), no videos, no profiles.

## Operating Context
A TV across the room, evenings under lamp light and daytime in a bright room. Arrow keys or the phone's D-pad move a
focus; numbers open channels. Older PCs: Windows 7 SP1 to 11.

## Capabilities and Constraints
- Channels: up to 30, each a web site or a program; a number on the remote opens one.
- News from one RSS feed, a 5-day forecast (Open-Meteo, no key), a photo slideshow from a local folder.
- Phone pairing by QR code and a six-digit code; only the local network can reach the remote.
- No accounts, no analytics, no admin rights to install.

## Brand Commitments
Modern, warm, calm; readable from the sofa. Evening (dark) and Daylight (light) looks, five accents.

## Evidence on Hand
The 2026-11-15 cloud-session description of the approved design (the first build was lost before it reached GitHub).

## Product Principles
- Readable at three metres: big type, one obvious focus.
- Nothing happens that the person on the sofa did not ask for.
- Works offline for everything but weather and news.

## Accessibility & Inclusion
High contrast in both looks, focus always visible, no information by colour alone (channel numbers beside the
coloured initials), motion reduced when the system asks for it.

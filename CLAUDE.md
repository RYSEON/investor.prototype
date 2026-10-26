# RYSEON — investor link

Live: https://ryseon.github.io/investor.prototype/  (personal link per investor: `…/?r=<id>`)

**This repo is generated. Never edit the app here.**
The app is `src/prototype.html` on `main` of `SportynX/sportynx-ryse-prototype-` (Ivan's working repo, test link
https://sportynx.github.io/sportynx-ryse-prototype-/ — never sent to investors). Every change made there reaches this
link automatically: `.github/workflows/sync.yml` runs every 15 minutes, takes the latest app, runs the source repo's own
`build.py`, then `tools/investor_build.py` adds only investor things, and force-publishes the result to the `gh-pages`
branch (one commit, no history). It publishes only when the source or the investor files changed.

What lives here (and only here):
- `investors.json` — personal links. `id` is the `?r=` value (lowercase a–z, 0–9, `-`, `_`), `name` is shown in PostHog.
  Each id gets its own manifest (`m/<id>.webmanifest`, start_url `../?r=<id>`) so the link survives "Add to Home Screen".
- `config.json` — PostHog key (EU, cookieless: memory persistence, no banner), session replay switch, investor tweaks
  (`hide_preview_helpers` hides the "Prototype · preview a state" groups). Ask Ivan before changing any tweak.
- `tools/investor_build.py` — the investor layer: `?r=` (saved in localStorage, kept through the auto-update reload),
  PostHog events: `app_open`, `screen_view` (hooked on `window.ryseOnEnter`, English screen names from the source markup),
  `tab_switch`, `settings_open` / `settings_page`, `demo_profile_opened`, `app_resume`, `session_end` (seconds visible),
  plus autocapture of taps. If the source build changes shape the script stops with a clear error instead of guessing.
- `icons/` — investor Home Screen icon (black R, Ivan 24 Oct); replaces the source icons only on this link.
- `assets/preview-player.jpg` + `preview_photo` in config — if a player skips the profile photo (or reaches Home
  without one), this photo is added through the app's own photo input with the message "Photo added for preview".
- `install_guide` + `assets/guide/` — welcome screen in a phone browser (never in the Home Screen app): "Which phone?"
  iPhone / Android, then the three Add to Home Screen steps on one screen; "Continue in browser" is remembered. On a
  computer it shows the investor's QR code (`qr/<id>.png`, generated in the build with `qrcode`). Events: guide_shown,
  guide_os, guide_closed. `?guide=1` shows the welcome again (Ivan testing). Branded QR cards for Ivan are a PDF per investor
  (RYSEON-QR-<id>.pdf: QR with the R icon, error correction H, plus a tappable "Open RYSEON" button linking the same URL) and a PNG; they are
  made on request and checked with OpenCV's QR decoder before sending.
- `resume_hint` — on the language screen, if a saved player exists (`ryse-last-profile`), a quiet "Welcome back, <name>.
  Hold Continue to jump back in." line above Continue plus a gentle fill on the button. The source app's one-time
  Gvardiol test-profile migrations (`ryse-mig-jg`, `ryse-mig-def`) are pre-set here so holding brings back the
  investor's own player. Events: resume_hint_shown, resume_by_hold.
- `pro_photos` + `assets/pros/` — "I'm already a pro": picking Joško Gvardiol, Luka Modrić, Mateo Kovačić, Marco Verratti (Al Duhail) or Harry Kane (Bayern) in Find
  yourself puts that player's photo in on the photo screen (s06), with "Photo added for preview". Event: pro_photo_added.
- `assets/crests/<key>.png` — investor-only club crests for the Home club chip (top right): `milan` (AC Milan, Modrić);
  `alduhail` (Al Duhail, Verratti; logo from Ivan 26 Oct);
  `bayern` (Bayern München, Kane; logo + photo from Ivan 26 Oct). Manchester City (Gvardiol, Kovačić) comes from the source app.
- `vendor/posthog.js` — posthog-js `dist/array.js` (Apache-2.0), served as `ph.js`.

Never put analytics or investor code into the source repo. Talk to Ivan in Croatian; he is not a developer — do all
git/deploy work yourself.

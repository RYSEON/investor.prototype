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
- `vendor/posthog.js` — posthog-js `dist/array.js` (Apache-2.0), served as `ph.js`.

Never put analytics or investor code into the source repo. Talk to Ivan in Croatian; he is not a developer — do all
git/deploy work yourself.

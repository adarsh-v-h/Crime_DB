# Frontend — modular source

The UI is a React single-page app that runs **without a bundler** (CDN React +
in-browser Babel). To keep it editable and scalable, the source is split into
small modules under `src/` and assembled into the single file Flask serves.

## Structure

```
Frontend/
├── index.template.html   # HTML shell (head, CDN scripts, body) with two
│                         #   placeholders: __STYLES__ and __APP_JS__
├── src/
│   ├── styles.css        # all global CSS (editorial design system)
│   ├── 00-config.jsx     # API base, auth/session helpers, apiFetch, reCAPTCHA
│   ├── 01-icons.jsx      # <Icon> component (SVG paths)
│   ├── 02-shared.jsx     # AnimatedCounter, Particles, motion variants,
│   │                     #   shared style constants, editorial image consts
│   ├── 03-layout.jsx     # HeroVideoBackground, CrmsPageHeader, CrmsPageShell
│   ├── 04-LandingPage.jsx
│   ├── 05-PublicPortal.jsx     # complaint intake, browse, access request
│   ├── 06-StaffDashboard.jsx   # officer case desk + access requests
│   ├── 07-AdminDashboard.jsx   # admin overview + all-cases
│   ├── 08-LoginPage.jsx
│   └── 09-App.jsx        # root component + ReactDOM.createRoot/render
├── build.py              # assembles src/ -> crms_frontend.html
└── crms_frontend.html    # GENERATED — do not edit by hand
```

## Workflow

1. Edit the relevant file in `src/` (or `index.template.html` / `src/styles.css`).
2. Rebuild:
   ```bash
   python3 Frontend/build.py
   ```
3. Reload the app (Flask serves `crms_frontend.html` at `/`).

> **Never edit `crms_frontend.html` directly** — it is regenerated from `src/`
> and your changes would be overwritten. Treat it as a build artifact.

## Why a build step instead of separate `<script>` tags?

With in-browser Babel, loading each module as its own
`<script type="text/babel">` transforms each file in isolation (cross-file
references can break) and adds one network request + one transform per file on
every page load. Concatenating at build time keeps the served file identical to
the original monolith — **same runtime behaviour, same performance** — and needs
no Node/bundler on the server (important: Render runs the Python service only).

## Guard against drift

`build.py --check` rebuilds in memory and exits non-zero if `crms_frontend.html`
is stale relative to `src/`. Useful as a pre-commit / CI check:

```bash
python3 Frontend/build.py --check
```

## Module load order

Order matters (definitions must precede first use; `App` + render are last). It
is defined in `MODULE_ORDER` inside `build.py`. The numeric filename prefixes
mirror that order for readability.

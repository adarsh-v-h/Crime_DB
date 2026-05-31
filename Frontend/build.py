#!/usr/bin/env python3
"""
Frontend build: assembles the modular sources in src/ into the single
crms_frontend.html that Flask serves.

Why a build step (and not separate <script> tags)?
  The app uses in-browser Babel (no bundler). Loading each module as its own
  <script type="text/babel"> would transform each file in isolation and can
  break cross-file references, and adds N network round-trips + N transforms on
  every page load. Concatenating here keeps the served file byte-identical to
  the old monolith — same runtime behaviour, same performance, no Node required
  on the server.

Usage:
    python3 build.py            # build crms_frontend.html from src/
    python3 build.py --check    # build to memory and fail if it differs from
                                 # the committed crms_frontend.html (CI guard)

Edit the files in src/ — never edit crms_frontend.html by hand (it is generated).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
TEMPLATE = os.path.join(HERE, "index.template.html")
OUTPUT = os.path.join(HERE, "crms_frontend.html")

# JSX modules concatenated in this exact order (order matters: definitions must
# precede their first use, and App/render come last).
MODULE_ORDER = [
    "00-config.jsx",
    "01-icons.jsx",
    "02-shared.jsx",
    "03-layout.jsx",
    "04-LandingPage.jsx",
    "05-PublicPortal.jsx",
    "06-StaffDashboard.jsx",
    "07-AdminDashboard.jsx",
    "08-LoginPage.jsx",
    "09-App.jsx",
]


def build() -> str:
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()

    with open(os.path.join(SRC, "styles.css"), encoding="utf-8") as f:
        styles = f.read()

    app_js = "".join(
        open(os.path.join(SRC, name), encoding="utf-8").read()
        for name in MODULE_ORDER
    )

    if "__STYLES__\n" not in template or "__APP_JS__\n" not in template:
        raise SystemExit("Template is missing __STYLES__ or __APP_JS__ placeholder.")

    return template.replace("__STYLES__\n", styles, 1).replace("__APP_JS__\n", app_js, 1)


def main():
    result = build()
    if "--check" in sys.argv:
        existing = open(OUTPUT, encoding="utf-8").read() if os.path.exists(OUTPUT) else ""
        if existing != result:
            print("OUT OF DATE: crms_frontend.html does not match src/. Run: python3 build.py")
            sys.exit(1)
        print("OK: crms_frontend.html is up to date with src/.")
        return
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(result)
    print(f"Built {os.path.relpath(OUTPUT, HERE)} from {len(MODULE_ORDER)} modules + styles.css")


if __name__ == "__main__":
    main()

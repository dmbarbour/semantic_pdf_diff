"""What every generated HTML page shares (code review 2026-10-01: nine pages, each with its own palette and
escaping, and JSON injected by hand twice): escaping, data embedded in a page, the page's head, and a palette of
colour tokens with a dark mode.
"""
import html
import json

def esc(value):
    """Text as HTML (quotes too, so it's safe in attributes)."""
    return html.escape(str(value), quote=True)

def embed_json(data):
    """Data as JSON safe inside a <script> element (no "</" to close it early)."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

def fill(template, title, data):
    """A page template's __TITLE__ and __DATA__ filled in."""
    return template.replace("__TITLE__", esc(title)).replace("__DATA__", embed_json(data))

# Colour tokens, light and dark (the system's choice, or data-theme on the root element).
PALETTE = """
:root{--bg:#edf2f6;--fg:#183047;--muted:#536879;--accent:#356783;--card:#ffffff;--panel:#f7f9fb;--line:#d7e1e8;
--rule:#83a9bf;--field:#aac0cd;--warn:#854400}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#12171c;--fg:#e3e9ee;--muted:#9aa9b6;
--accent:#8cb8d4;--card:#1b232b;--panel:#202a33;--line:#2f3b46;--rule:#4f7690;--field:#4a5d6c;--warn:#e0a35c}}
:root[data-theme="dark"]{--bg:#12171c;--fg:#e3e9ee;--muted:#9aa9b6;--accent:#8cb8d4;--card:#1b232b;--panel:#202a33;
--line:#2f3b46;--rule:#4f7690;--field:#4a5d6c;--warn:#e0a35c}
body{background:var(--bg);color:var(--fg)}
"""

def page(title, body, style="", palette=True):
    """A whole page: its head (charset, viewport, title, the palette and the page's own style) and body."""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f'<style>{PALETTE if palette else ""}{style}</style></head><body>{body}</body></html>')

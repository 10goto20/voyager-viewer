#!/usr/bin/env python3
"""
voyager_viewer.py — Standalone GraphQL Voyager desktop viewer

Usage:
    python voyager_viewer.py [schema_file] [--theme dark|light] [--port PORT]

Requirements:
    pip install pywebview

    Linux also needs: sudo apt install python3-gi gir1.2-webkit2-4.1
                      (or gir1.2-webkit2-4.0 on older distros)

Assets (must live alongside this script):
    voyager.standalone.js
    voyager.css
"""

import argparse
import http.server
import json
import pathlib
import socket
import sys
import threading
import urllib.parse
from datetime import datetime


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# ── HTML shell ────────────────────────────────────────────────────────────────
# Braces are doubled ({{ }}) because this string is later fed to str.format()

HTML = """\
<!DOCTYPE html>
<html data-theme="{theme}">
<head>
  <meta charset="utf-8" />
  <title>GraphQL Voyager</title>
  <link rel="stylesheet" href="/voyager.css" />
  <script src="/voyager.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ height: 100%; overflow: hidden; }}

    /* ── Toolbar ── */
    #toolbar {{
      position: fixed; top: 0; left: 0; right: 0; height: 40px;
      display: flex; align-items: center; gap: 8px;
      padding: 0 14px; z-index: 10000;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      font-size: 13px;
    }}
    [data-theme="dark"]  #toolbar {{
      background: #1c1c1c; border-bottom: 1px solid #333; color: #c9c9c9;
    }}
    [data-theme="light"] #toolbar {{
      background: #f0f0f0; border-bottom: 1px solid #ccc; color: #333;
    }}

    #schema-label {{
      flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      font-weight: 500;
    }}
    #schema-size {{ opacity: 0.5; font-size: 11px; flex-shrink: 0; }}

    .tb-btn {{
      border: none; cursor: pointer; border-radius: 5px;
      padding: 4px 11px; font-size: 12px; font-family: inherit; flex-shrink: 0;
      transition: background 0.15s;
    }}
    [data-theme="dark"]  .tb-btn {{ background: #2e2e2e; color: #ccc; }}
    [data-theme="dark"]  .tb-btn:hover {{ background: #3d3d3d; }}
    [data-theme="light"] .tb-btn {{ background: #ddd; color: #333; }}
    [data-theme="light"] .tb-btn:hover {{ background: #c8c8c8; }}

    /* ── Voyager container ── */
    #voyager {{ height: calc(100vh - 40px); margin-top: 40px; }}

    /* ═══════════════════════════════════════════════════════════════
       HIGH-CONTRAST DARK MODE
       Applied uniformly to the doc panel, graph canvas, and all
       MUI components. No filter hacks — every color explicitly set.

       Palette
       ─────────────────────────────────────────────────────────────
       bg-base      #111111   overall / graph background
       bg-panel     #161616   left panel, menu-content
       bg-surface   #1e1e1e   elevated elements (popover, dropdown)
       bg-hover     rgba(0,188,212,.10)
       bg-selected  rgba(0,188,212,.18)
       border       #2a2a2a
       text         #f0f0f0   primary text
       text-dim     #aaaaaa   secondary / muted text
       accent       #00bcd4   cyan (unchanged hue, same as light theme)
       blue         #64b5f6   field-names, nav links  (was dark #224d6f)
       blue-hi      #90caf9   hover for blue
       orange       #ffb74d   arg-names               (was #c77f53)
       rose         #f48a8a   scalar/built-in types   (was maroon #711c1c)
       alert        #ef5350   error text              (was dark #b71c1c)
       node-bg      #152028   graph node body fill
       node-border  #2a6070   graph node stroke
       node-header  #0c3d4e   graph node title bar
       node-sel     #00838f   selected node header
       edge         #2a6070   edge path / arrowhead
       ═══════════════════════════════════════════════════════════════ */

    /* ── Global background (covers the graph area too) ─────────────── */
    [data-theme="dark"] body,
    [data-theme="dark"] #voyager,
    [data-theme="dark"] .graphql-voyager              {{ background: #111111; color: #f0f0f0; }}

    /* ── Left panel ────────────────────────────────────────────────── */
    [data-theme="dark"] .graphql-voyager > .doc-panel {{ background: #161616 !important; }}
    [data-theme="dark"] .doc-panel > .contents        {{ background: #161616 !important; border-right-color: #2a2a2a !important; }}
    [data-theme="dark"] .doc-wrapper                  {{ background: #161616 !important; }}
    [data-theme="dark"] .type-doc > div               {{ background: #161616 !important; }}
    [data-theme="dark"] .type-info-popover {{
      background: #1e1e1e !important;
      border-color: #2a2a2a !important;
      box-shadow: 0 0 14px 4px rgba(0,0,0,.8) !important;
    }}

    /* ── Navigation bar ────────────────────────────────────────────── */
    [data-theme="dark"] .doc-navigation               {{ border-bottom-color: #2a2a2a !important; }}
    [data-theme="dark"] .doc-navigation > .back       {{ color: #64b5f6 !important; }}
    [data-theme="dark"] .doc-navigation > .back:before {{ border-left-color: #64b5f6 !important; border-top-color: #64b5f6 !important; }}
    [data-theme="dark"] .doc-navigation > .header     {{ color: #aaaaaa !important; }}
    [data-theme="dark"] .doc-navigation > .active     {{ color: #00bcd4 !important; }}

    /* ── Category / field list ─────────────────────────────────────── */
    [data-theme="dark"] .doc-category > .title        {{ color: #aaaaaa !important; border-bottom-color: #2a2a2a !important; }}
    [data-theme="dark"] .doc-category > .item         {{ color: #e0e0e0 !important; }}
    [data-theme="dark"] .doc-category > .item:nth-child(odd) {{ background-color: rgba(255,255,255,.025) !important; }}
    [data-theme="dark"] .doc-category > .item:hover   {{ background-color: rgba(0,188,212,.10) !important; }}
    [data-theme="dark"] .doc-category > .item.-selected {{ background-color: rgba(0,188,212,.18) !important; border-left-color: #00bcd4 !important; }}
    [data-theme="dark"] .doc-category > .item.-with-args:before {{ border-top-color: #64b5f6 !important; }}

    /* ── Syntax / token colors ─────────────────────────────────────── */
    [data-theme="dark"] .field-name                       {{ color: #64b5f6 !important; }}
    [data-theme="dark"] .type-name + .field-name::before  {{ color: #aaaaaa !important; }}
    [data-theme="dark"] .value-name                       {{ color: #4fc3f7 !important; }}
    [data-theme="dark"] .arg-name                         {{ color: #ffb74d !important; }}
    [data-theme="dark"] .arg-wrap > .arg > .default-value {{ color: #4fc3f7 !important; }}
    [data-theme="dark"] .doc-alert-text                   {{ color: #ef5350 !important; }}
    [data-theme="dark"] .type-doc > .loading              {{ color: #aaaaaa !important; }}

    [data-theme="dark"] .type-name.-input-obj,
    [data-theme="dark"] .type-name.-object                {{ color: #64b5f6 !important; }}
    [data-theme="dark"] .type-name.-input-obj:hover,
    [data-theme="dark"] .type-name.-object:hover          {{ color: #90caf9 !important; }}

    [data-theme="dark"] .type-name.-scalar,
    [data-theme="dark"] .type-name.-built-in              {{ color: #f48a8a !important; }}
    [data-theme="dark"] .type-name.-scalar:hover,
    [data-theme="dark"] .type-name.-built-in:hover        {{ color: #ffcdd2 !important; }}

    /* ── Descriptions ──────────────────────────────────────────────── */
    [data-theme="dark"] .arg-wrap.-expanded .arg-description {{ color: #aaaaaa !important; }}
    [data-theme="dark"] .description-box.-no-description  {{ color: #666666 !important; }}
    [data-theme="dark"] .description-box blockquote       {{ border-left-color: rgba(0,188,212,.4) !important; }}

    /* ── Bottom settings/selector box (.menu-content) ─────────────── */
    [data-theme="dark"] .graphql-voyager > .menu-content {{
      background: #1e1e1e !important;
      border-color: #2a2a2a !important;
      box-shadow: 0 4px 12px rgba(0,0,0,.7) !important;
    }}
    [data-theme="dark"] .graphql-voyager > .menu-content .setting-other-options label,
    [data-theme="dark"] .graphql-voyager > .menu-content .MuiFormControlLabel-label {{ color: #f0f0f0 !important; }}
    [data-theme="dark"] .graphql-voyager > .menu-content .MuiInputBase-root         {{ color: #f0f0f0 !important; }}
    [data-theme="dark"] .graphql-voyager > .menu-content .MuiInput-underline:before {{ border-bottom-color: #444 !important; }}
    [data-theme="dark"] .graphql-voyager > .menu-content .MuiSelect-icon            {{ color: #aaa !important; }}

    /* ── MUI global overrides ──────────────────────────────────────── */
    [data-theme="dark"] .MuiPaper-root                   {{ background-color: #1e1e1e !important; color: #f0f0f0 !important; }}
    [data-theme="dark"] .MuiTypography-root,
    [data-theme="dark"] .MuiInputBase-root,
    [data-theme="dark"] .MuiFormLabel-root,
    [data-theme="dark"] .MuiFormControlLabel-label       {{ color: #f0f0f0 !important; }}
    [data-theme="dark"] .MuiOutlinedInput-notchedOutline {{ border-color: #444 !important; }}
    [data-theme="dark"] .MuiCheckbox-root svg,
    [data-theme="dark"] .MuiSwitch-thumb                 {{ color: #00bcd4 !important; }}
    [data-theme="dark"] .MuiDivider-root                 {{ border-color: #2a2a2a !important; }}
    [data-theme="dark"] .MuiMenu-paper,
    [data-theme="dark"] .MuiPopover-paper                {{ background-color: #1e1e1e !important; color: #f0f0f0 !important; }}
    [data-theme="dark"] .MuiMenuItem-root                {{ color: #f0f0f0 !important; }}
    [data-theme="dark"] .MuiMenuItem-root:hover,
    [data-theme="dark"] .MuiMenuItem-root.Mui-selected   {{ background-color: #2a2a2a !important; }}

    /* ── Graph canvas — direct SVG color overrides ─────────────────── */
    /* These replace the invert-filter hack with explicit per-element   */
    /* colors so the graph matches the panel palette exactly.           */

    /* Node bodies */
    [data-theme="dark"] .node polygon                      {{ stroke: #2a6070; fill: #152028; }}
    [data-theme="dark"] .node .type-title polygon          {{ fill: #0c3d4e; }}
    [data-theme="dark"] .node text                         {{ fill: #e0e0e0; }}
    [data-theme="dark"] .node .type-title text             {{ fill: #f0f0f0; }}
    [data-theme="dark"] .node.selected polygon             {{ stroke: #00bcd4; stroke-width: 3; }}
    [data-theme="dark"] .node.selected .type-title polygon {{ fill: #00838f; }}

    /* Edges */
    [data-theme="dark"] .edge path                         {{ stroke: #2a6070; }}
    [data-theme="dark"] .edge.highlighted path:not(.hover-path),
    [data-theme="dark"] .edge.hovered     path:not(.hover-path),
    [data-theme="dark"] .edge:hover       path:not(.hover-path) {{ stroke: #00bcd4; }}
    [data-theme="dark"] .edge polygon                      {{ fill: #2a6070; stroke: #2a6070; }}
    [data-theme="dark"] .edge.highlighted polygon,
    [data-theme="dark"] .edge.hovered     polygon,
    [data-theme="dark"] .edge:hover       polygon          {{ stroke: #00bcd4; fill: #00bcd4; }}
    [data-theme="dark"] .edge text                         {{ fill: #4dd0e1; }}
    [data-theme="dark"] .edge.selected path:not(.hover-path) {{ stroke: #ef5350; }}
    [data-theme="dark"] .edge.selected polygon             {{ stroke: #ef5350; fill: #ef5350; }}

    /* Selected field highlight */
    [data-theme="dark"] .field.selected > polygon          {{ fill: rgba(239,83,80,.20); }}

    /* SVG type-link text labels */
    [data-theme="dark"] .type-link                         {{ fill: #64b5f6; }}
    [data-theme="dark"] .type-link:hover                   {{ fill: #90caf9; }}

    /* Eye / visibility button */
    [data-theme="dark"] .eye-button svg path:not([fill])   {{ fill: #00bcd4; }}

    /* ── Toast notification ── */
    #toast {{
      display: none; position: fixed; bottom: 14px; right: 14px;
      padding: 7px 16px; border-radius: 6px; z-index: 10001;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 12px; border-left: 3px solid #4caf50;
    }}
    [data-theme="dark"]  #toast {{ background: #2a2a2a; color: #ccc; }}
    [data-theme="light"] #toast {{ background: #f5f5f5; color: #333; box-shadow: 0 2px 8px rgba(0,0,0,.15); }}
    #toast.error {{ border-left-color: #f44336 !important; }}
  </style>
</head>
<body>

<div id="toolbar">
  <span id="schema-label">Loading…</span>
  <span id="schema-size"></span>
  <button class="tb-btn" onclick="openFile()">Open…</button>
  <button class="tb-btn" onclick="reloadSchema()">⟳ Reload</button>
  <button class="tb-btn" onclick="toggleTheme()">◑ Theme</button>
</div>

<div id="voyager"></div>
<div id="toast"></div>

<script>
  // ── Schema loading ──────────────────────────────────────────────────────────

  async function loadSchema() {{
    try {{
      const res = await fetch('/schema');
      if (res.status === 204) return; // no schema loaded yet
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const fmt = res.headers.get('X-Schema-Format');
      let introspection;
      if (fmt === 'sdl') {{
        const sdl = await res.text();
        introspection = GraphQLVoyager.sdlToSchema(sdl);
      }} else {{
        introspection = await res.json();
      }}
      renderVoyager(introspection);
      await refreshToolbar();
    }} catch (e) {{
      toast('Error loading schema: ' + e.message, true);
    }}
  }}

  function renderVoyager(schema) {{
    const el = document.getElementById('voyager');
    el.innerHTML = '';
    GraphQLVoyager.renderVoyager(el, {{ introspection: schema }});
  }}

  async function reloadSchema() {{
    toast('Reloading…');
    try {{
      const res = await fetch('/reload', {{ method: 'POST' }});
      const data = await res.json();
      if (data.ok) {{
        await loadSchema();
        toast('Reloaded: ' + data.file);
      }} else {{
        toast('Reload failed: ' + (data.error || 'unknown error'), true);
      }}
    }} catch (e) {{
      toast('Reload error: ' + e.message, true);
    }}
  }}

  async function openFile() {{
    try {{
      const path = await window.pywebview.api.open_file_dialog();
      if (!path) return;
      toast('Loading ' + path + '…');
      const res = await fetch('/reload', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ path }})
      }});
      const data = await res.json();
      if (data.ok) {{
        await loadSchema();
        toast('Loaded: ' + data.file);
      }} else {{
        toast('Failed: ' + (data.error || 'unknown error'), true);
      }}
    }} catch (e) {{
      toast('Error: ' + e.message, true);
    }}
  }}

  // ── Toolbar helpers ─────────────────────────────────────────────────────────

  async function refreshToolbar() {{
    try {{
      const s = await (await fetch('/status')).json();
      if (!s.loaded) {{
        document.getElementById('schema-label').textContent = 'No schema loaded';
        document.getElementById('schema-size').textContent = '';
        return;
      }}
      document.getElementById('schema-label').textContent = s.file;
      document.getElementById('schema-size').textContent =
        '(' + (s.size / 1024).toFixed(0) + ' KB)';
      if (window.pywebview) {{
        window.pywebview.api.set_title('GraphQL Voyager — ' + s.file);
      }}
    }} catch (_) {{}}
  }}

  function toggleTheme() {{
    const html = document.documentElement;
    html.dataset.theme = html.dataset.theme === 'dark' ? 'light' : 'dark';
  }}

  // ── Toast ───────────────────────────────────────────────────────────────────

  let _toastTimer = null;
  function toast(msg, isError = false) {{
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = isError ? 'error' : '';
    el.style.display = 'block';
    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(() => {{ el.style.display = 'none'; }}, 3000);
  }}

  // ── Init ────────────────────────────────────────────────────────────────────
  // pywebview injects window.pywebview.api asynchronously; wait for it.

  function waitForBridge(cb, tries = 30) {{
    if (window.pywebview && window.pywebview.api) {{ cb(); return; }}
    if (tries <= 0) {{ cb(); return; }}
    setTimeout(() => waitForBridge(cb, tries - 1), 100);
  }}

  async function init() {{
    const s = await (await fetch('/status')).json();
    if (s.loaded) {{
      await loadSchema();
    }} else {{
      document.getElementById('schema-label').textContent = 'No schema loaded';
      document.getElementById('schema-size').textContent = '';
    }}
  }}

  waitForBridge(init);
</script>
</body>
</html>
"""


# ── Server state ──────────────────────────────────────────────────────────────

class AppState:
    """Shared mutable state between the HTTP handler and the app."""

    SDL_EXTENSIONS = {'.graphql', '.graphqls'}

    def __init__(self, schema_path: pathlib.Path | None, theme: str):
        self.theme = theme
        self.schema_path = schema_path.resolve() if schema_path else None
        self.schema_content = None   # raw text (JSON or SDL)
        self.schema_format = None    # 'introspection' | 'sdl'
        self.loaded_at = None
        self.html = HTML.format(theme=theme)
        self._lock = threading.Lock()
        if schema_path:
            self.load_schema()

    def load_schema(self, new_path: str = None):
        if new_path:
            p = pathlib.Path(new_path).resolve()
        elif self.schema_path:
            p = self.schema_path
        else:
            raise ValueError('No schema path specified')

        fmt = 'sdl' if p.suffix.lower() in self.SDL_EXTENSIONS else 'introspection'
        raw = p.read_text(encoding='utf-8')
        if fmt == 'introspection':
            json.loads(raw)  # validate — raises ValueError on bad JSON

        with self._lock:
            self.schema_path = p
            self.schema_content = raw
            self.schema_format = fmt
            self.loaded_at = datetime.now().isoformat(timespec='seconds')

    def info(self) -> dict:
        with self._lock:
            if self.schema_path is None or self.schema_content is None:
                return {'loaded': False, 'file': None, 'path': None, 'size': 0,
                        'format': None, 'loaded_at': None}
            return {
                'loaded': True,
                'file': self.schema_path.name,
                'path': str(self.schema_path),
                'size': len(self.schema_content),
                'format': self.schema_format,
                'loaded_at': self.loaded_at,
            }

    def get_schema(self) -> tuple[str, str] | tuple[None, None]:
        """Returns (content, format) or (None, None) if no schema loaded."""
        with self._lock:
            return self.schema_content, self.schema_format


# ── HTTP handler ──────────────────────────────────────────────────────────────

class VoyagerHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        dispatch = {
            '/':            self._html,
            '/voyager.js':  lambda: self._asset('voyager.standalone.js', 'application/javascript'),
            '/voyager.css': lambda: self._asset('voyager.css', 'text/css'),
            '/schema':      self._schema,
            '/status':      self._status,
        }
        fn = dispatch.get(path)
        if fn:
            fn()
        else:
            self._send(404, 'text/plain', b'Not found')

    def do_POST(self):
        if self.path != '/reload':
            self._send(404, 'text/plain', b'Not found')
            return

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'
        try:
            payload = json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            payload = {}

        new_path = payload.get('path')
        try:
            self.server.state.load_schema(new_path)
            self._send(200, 'application/json',
                       json.dumps({'ok': True, **self.server.state.info()}).encode())
        except FileNotFoundError as e:
            self._send(200, 'application/json',
                       json.dumps({'ok': False, 'error': f'File not found: {e}'}).encode())
        except ValueError as e:
            self._send(200, 'application/json',
                       json.dumps({'ok': False, 'error': f'Invalid JSON: {e}'}).encode())
        except Exception as e:
            self._send(200, 'application/json',
                       json.dumps({'ok': False, 'error': str(e)}).encode())

    # ── Response helpers ──────────────────────────────────────────────────────

    def _html(self):
        body = self.server.state.html.encode('utf-8')
        self._send(200, 'text/html; charset=utf-8', body)

    def _asset(self, filename: str, content_type: str):
        p = SCRIPT_DIR / filename
        try:
            self._send(200, content_type, p.read_bytes())
        except FileNotFoundError:
            self._send(404, 'text/plain', f'Missing asset: {filename}'.encode())

    def _schema(self):
        content, fmt = self.server.state.get_schema()
        if content is None:
            self._send(204, 'text/plain', b'', extra_headers={'X-Schema-Format': 'none'})
            return
        content_type = 'application/json' if fmt == 'introspection' else 'text/plain; charset=utf-8'
        self._send(200, content_type, content.encode('utf-8'),
                   extra_headers={'X-Schema-Format': fmt})

    def _status(self):
        self._send(200, 'application/json',
                   json.dumps(self.server.state.info()).encode())

    def _send(self, code: int, content_type: str, body: bytes, extra_headers: dict = {}):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        for k, v in extra_headers.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass  # suppress request logging


# ── pywebview JS API ──────────────────────────────────────────────────────────

class VoyagerAPI:
    """Methods exposed to JavaScript as window.pywebview.api.*"""

    def open_file_dialog(self):
        """Open a native OS file picker and return the chosen path (or None)."""
        import webview
        result = webview.windows[0].create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=('GraphQL Schema (*.json;*.graphql;*.graphqls)', 'All Files (*.*)')
        )
        if result:
            return result[0] if isinstance(result, (list, tuple)) else result
        return None

    def set_title(self, title: str):
        """Update the window title bar."""
        import webview
        webview.windows[0].set_title(title)


# ── Utilities ─────────────────────────────────────────────────────────────────

def find_free_port(preferred: int) -> int:
    """Return preferred port if free, otherwise any available port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', preferred))
            return preferred
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]


def start_server(state: AppState, port: int) -> http.server.HTTPServer:
    server = http.server.HTTPServer(('127.0.0.1', port), VoyagerHandler)
    server.state = state
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='GraphQL Voyager — standalone desktop viewer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            'examples:\n'
            '  python voyager_viewer.py\n'
            '  python voyager_viewer.py myschema.json\n'
            '  python voyager_viewer.py myschema.json --theme light\n'
        )
    )
    parser.add_argument(
        'schema', nargs='?', default=None,
        help='Path to schema file (.json introspection, .graphql, or .graphqls — optional)'
    )
    parser.add_argument(
        '--theme', choices=['dark', 'light'], default='dark',
        help='Initial colour theme (default: dark)'
    )
    parser.add_argument(
        '--port', type=int, default=7745,
        help='Internal HTTP server port (default: 7745)'
    )
    args = parser.parse_args()

    # ── Resolve schema path (optional) ────────────────────────────────────────
    schema_path = None
    if args.schema:
        schema_path = pathlib.Path(args.schema)
        if not schema_path.is_absolute():
            schema_path = pathlib.Path.cwd() / schema_path
        if not schema_path.exists():
            sys.exit(f'Error: schema file not found: {schema_path}')

    # ── Check required assets ──────────────────────────────────────────────────
    missing = [a for a in ('voyager.standalone.js', 'voyager.css')
               if not (SCRIPT_DIR / a).exists()]
    if missing:
        sys.exit(
            'Error: missing asset(s) in the same directory as voyager_viewer.py:\n'
            + '\n'.join(f'  {SCRIPT_DIR / a}' for a in missing)
        )

    # ── Import pywebview with a clear error message ────────────────────────────
    try:
        import webview
    except ImportError:
        sys.exit(
            'Error: pywebview is not installed.\n\n'
            'Install it with:\n'
            '    pip install pywebview\n\n'
            'On Linux you also need:\n'
            '    sudo apt install python3-gi gir1.2-webkit2-4.1\n'
            '    (or gir1.2-webkit2-4.0 on older distributions)\n'
        )

    # ── Start embedded HTTP server ─────────────────────────────────────────────
    port = find_free_port(args.port)
    state = AppState(schema_path, args.theme)
    start_server(state, port)

    # ── Open desktop window ────────────────────────────────────────────────────
    # pywebview automatically selects the right backend for the current OS:
    #   macOS   → WKWebView
    #   Windows → WebView2 (Edge) / MSHTML fallback
    #   Linux   → WebKitGTK

    window = webview.create_window(
        title=f'GraphQL Voyager — {schema_path.name}' if schema_path else 'GraphQL Voyager',
        url=f'http://127.0.0.1:{port}/',
        js_api=VoyagerAPI(),
        width=1400,
        height=900,
        min_size=(800, 600),
        resizable=True,
    )

    try:
        webview.start(debug=False)
    except Exception as e:
        if sys.platform.startswith('linux'):
            sys.exit(
                f'Error: failed to start webview ({e})\n\n'
                'On Linux, install the WebKitGTK backend:\n'
                '    sudo apt install python3-gi gir1.2-webkit2-4.1\n'
            )
        raise


if __name__ == '__main__':
    main()

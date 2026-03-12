# voyager-viewer

A standalone desktop application for exploring GraphQL schemas using
[GraphQL Voyager](https://github.com/graphql-kit/graphql-voyager). No browser
required — the viewer opens in its own native window powered by the operating
system's built-in web engine.

<img width="1514" height="881" alt="image" src="https://github.com/user-attachments/assets/09e9a10f-cda1-4b14-a2bf-09412a03c45c" />

---

## Features

- **Native desktop window** — opens as a proper application window, not a browser tab
- **Dark and light themes** — toggle with the toolbar button; defaults to dark
- **Load any schema** — open `.json` (introspection result), `.graphql`, or `.graphqls` files via the toolbar file picker or the command line
- **Live reload** — reload the current schema from disk without restarting
- **Full Voyager feature set** — interactive graph, type inspector, field filtering, root type selector, relay mode toggle, and more
- **Cross-platform** — macOS (WKWebView), Windows (WebView2 / Edge), Linux (WebKitGTK)
- **No server required** — everything runs locally; nothing leaves your machine

---

## Requirements

### Python

Python 3.10 or later is required.

### System web engine

| Platform | Engine | Notes |
|----------|--------|-------|
| macOS    | WKWebView | Built into macOS — no extra install needed |
| Windows  | WebView2  | Bundled with Windows 10/11 via Microsoft Edge |
| Linux    | WebKitGTK | Must be installed (see below) |

### Linux — WebKitGTK

On Debian/Ubuntu-based systems:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.1
```

On older distributions that only have WebKit 4.0:

```bash
sudo apt install python3-gi gir1.2-webkit2-4.0
```

---

## Installation

**1. Clone the repository**

```bash
git clone https://github.com/your-username/voyager-viewer.git
cd voyager-viewer
```

**2. Install the Python dependency**

```bash
pip install -r requirements.txt
```

> **Tip:** Using a virtual environment is recommended:
> ```bash
> python3 -m venv .venv
> source .venv/bin/activate   # Windows: .venv\Scripts\activate
> pip install -r requirements.txt
> ```

---

## Usage

### Open with no schema (use the file picker)

```bash
python3 voyager_viewer.py
```

Click **Open…** in the toolbar to load a schema file.

### Open a specific schema file

```bash
python3 voyager_viewer.py path/to/schema.graphql
python3 voyager_viewer.py path/to/introspection.json
python3 voyager_viewer.py path/to/schema.graphqls
```

### Options

```
usage: voyager_viewer.py [-h] [--theme {dark,light}] [--port PORT] [schema]

positional arguments:
  schema                Path to schema file (.json introspection, .graphql,
                        or .graphqls — optional)

options:
  --theme {dark,light}  Initial colour theme (default: dark)
  --port PORT           Internal HTTP server port (default: 7745)
  -h, --help            Show this help message and exit
```

### Examples

```bash
# Open in light mode
python3 voyager_viewer.py schema.graphql --theme light

# Use an introspection JSON export
python3 voyager_viewer.py exported-schema.json

# Use a custom port if 7745 is occupied
python3 voyager_viewer.py schema.graphql --port 8080
```

---

## Supported schema formats

| Extension | Format | Notes |
|-----------|--------|-------|
| `.json`   | Introspection result | The JSON response from a `{ __schema { ... } }` introspection query |
| `.graphql` | SDL | GraphQL Schema Definition Language |
| `.graphqls` | SDL | Alternative SDL extension, treated identically to `.graphql` |

To export an introspection result from a live API, you can use tools such as
[get-graphql-schema](https://github.com/nicolo-ribaudo/get-graphql-schema) or
the [GraphQL Playground](https://github.com/graphql/graphql-playground) export
feature.

---

## Toolbar

| Button | Action |
|--------|--------|
| **Open…** | Open a native file picker to load a new schema |
| **⟳ Reload** | Re-read the currently loaded schema file from disk |
| **◑ Theme** | Toggle between dark and light mode |

The toolbar also displays the name and size of the currently loaded schema.

---

## Sample schema

A sample schema (`schema.graphql`) is included in the repository. It models a
library management API and demonstrates common GraphQL patterns including:

- Object types with cross-references
- Cursor-based pagination (connections and edges)
- Input types and mutation payloads
- Enums and custom scalars
- Subscriptions

Open it to see what a populated Voyager graph looks like:

```bash
python3 voyager_viewer.py schema.graphql
```

---

## Project structure

```
voyager-viewer/
├── voyager_viewer.py        # Main application — run this
├── voyager.standalone.js    # GraphQL Voyager bundle (MIT) — see below
├── voyager.css              # GraphQL Voyager styles (MIT) — see below
├── schema.graphql           # Sample schema
├── requirements.txt         # Python dependencies
├── LICENSE                  # Project license
└── THIRD_PARTY_NOTICES.md   # Licenses for bundled third-party software
```

### Bundled Voyager assets

`voyager.standalone.js` and `voyager.css` are bundled directly in this
repository so the application works fully offline without making any outbound
network requests at runtime. Both files are taken from
[GraphQL Voyager](https://github.com/graphql-kit/graphql-voyager) **v2.0.0**
and are redistributed under its MIT license (see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

If you want to update to a newer release of Voyager, replace both files with
the corresponding build artefacts from the Voyager releases page:

```
https://github.com/graphql-kit/graphql-voyager/releases
```

The files to download are `voyager.standalone.js` and `voyager.css` from the
release assets.

> **Note:** The dark mode styles in `voyager_viewer.py` are keyed to the
> specific CSS class names and SVG structure used in Voyager v2.0.0. A new
> release may rename or restructure these, causing the dark theme to render
> incorrectly. After upgrading, verify dark mode and adjust the overrides in
> the `HTML` template string in `voyager_viewer.py` if needed.

---

## How it works

`voyager_viewer.py` spins up a minimal HTTP server on `127.0.0.1` (loopback
only — not accessible from the network) and opens a native desktop window
pointed at it using [pywebview](https://pywebview.flowrl.com). The Voyager
JavaScript and CSS are served as static assets; the schema is served from a
`/schema` endpoint so it can be reloaded without restarting the application.

The pywebview JS bridge (`window.pywebview.api`) is used for the native file
picker dialog, keeping all file-system access on the Python side.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for
details.

GraphQL Voyager (`voyager.standalone.js` and `voyager.css`) is also MIT
licensed and is bundled with permission — see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the full attribution.

#!/usr/bin/env python3
"""Build self-hosted technical documentation from the repository's Markdown files.

Only Python's standard library is required. HTML is fully static: no CDN or JS.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "apps/api/app/static/documentation"
SOURCES = {
    "index": ("docs/TECHNICAL.md", "Architektura"),
    "api": ("docs/API.md", "REST API"),
    "deployment": ("docs/DEPLOYMENT.md", "Wdrożenie"),
    "testing": ("docs/TESTING.md", "Testowanie"),
    "licenses": ("THIRD_PARTY_LICENSES.md", "Licencje"),
}
SOURCE_TO_PAGE = {Path(path).name: page for page, (path, _) in SOURCES.items()}


def inline(value: str) -> str:
    value = html.escape(value, quote=True)
    tokens: list[str] = []

    def hold(markup: str) -> str:
        tokens.append(markup)
        return f"\u0001{len(tokens) - 1}\u0002"

    value = re.sub(r"`([^`]+)`", lambda m: hold(f"<code>{m.group(1)}</code>"), value)

    def link(match: re.Match[str]) -> str:
        label, target = match.group(1), html.unescape(match.group(2))
        page = SOURCE_TO_PAGE.get(Path(target.split("#", 1)[0]).name)
        if page:
            dest = "index.html" if page == "index" else page + ".html"
        elif target.startswith(("https://", "http://")):
            dest = target
        else:
            return match.group(0)
        safe = html.escape(dest, quote=True)
        return hold(f'<a href="{safe}">{label}</a>')

    value = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    for i, markup in enumerate(tokens):
        value = value.replace(f"\u0001{i}\u0002", markup)
    return value


def slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).lower()
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def table(lines: list[str]) -> str:
    result = ['<div class="table-wrap"><table>']
    for index, row in enumerate(lines):
        if index == 1:
            continue
        cells = [x.strip() for x in row.strip().strip("|").split("|")]
        tag = "th" if index == 0 else "td"
        result.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
    result.append("</table></div>")
    return "\n".join(result)


def markdown_body(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    i = 0
    list_type = ""
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("```"):
            if list_type:
                output.append(f"</{list_type}>")
                list_type = ""
            language = line[3:].strip()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            safe = html.escape("\n".join(code))
            output.append(f'<pre><code class="lang-{html.escape(language)}">{safe}</code></pre>')
        elif re.match(r"^\|.*\|$", line) and i + 1 < len(lines) and re.fullmatch(
            r"\|[|:\-\s]+\|", lines[i + 1].strip()
        ):
            if list_type:
                output.append(f"</{list_type}>")
                list_type = ""
            rows = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i])
                i += 1
            output.append(table(rows))
            continue
        elif line.startswith("#"):
            if list_type:
                output.append(f"</{list_type}>")
                list_type = ""
            match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if match:
                level = len(match.group(1))
                label = match.group(2).strip()
                output.append(f'<h{level} id="{slug(label)}">{inline(label)}</h{level}>')
        elif not line.strip():
            if list_type:
                output.append(f"</{list_type}>")
                list_type = ""
        elif re.match(r"^\s*[-*]\s+", line) or re.match(r"^\s*\d+[.]\s+", line):
            ordered = bool(re.match(r"^\s*\d+[.]\s+", line))
            typ = "ol" if ordered else "ul"
            if list_type and list_type != typ:
                output.append(f"</{list_type}>")
                list_type = ""
            if not list_type:
                output.append(f"<{typ}>")
                list_type = typ
            label = re.sub(r"^\s*(?:[-*]|\d+[.])\s+", "", line)
            output.append(f"<li>{inline(label)}</li>")
        elif line.startswith(">"):
            if list_type:
                output.append(f"</{list_type}>")
                list_type = ""
            output.append(f"<blockquote>{inline(line.lstrip('> ').strip())}</blockquote>")
        else:
            if list_type:
                output.append(f"</{list_type}>")
                list_type = ""
            paragraph = [line]
            while (i + 1 < len(lines) and lines[i + 1].strip()
                   and not re.match(r"^(?:#{1,6}\s|[-*]\s|\d+[.]\s|\||```|>)", lines[i + 1])):
                i += 1
                paragraph.append(lines[i].strip())
            output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
        i += 1
    if list_type:
        output.append(f"</{list_type}>")
    return "\n".join(output)


CSS = """
:root{color-scheme:light;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--navy:#091735;--ink:#13264d;--muted:#52617c;--blue:#3157e9;--border:#dde4f0;--bg:#f5f7fc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);line-height:1.7}a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.header{background:#06112a;color:white;padding:14px max(22px,calc((100vw - 1240px)/2));display:flex;gap:24px;align-items:center;justify-content:space-between}
.header a{color:white}.brand{font-weight:800;letter-spacing:-.03em;font-size:20px}.brand span{color:#e969b7}.header .back{font-size:13px;color:#c5cde3}
.shell{display:grid;grid-template-columns:225px minmax(0,1fr);gap:32px;max-width:1260px;margin:0 auto;padding:36px 24px 70px}
.aside{align-self:start;position:sticky;top:24px}.aside h2{text-transform:uppercase;letter-spacing:.12em;font-size:11px;color:var(--muted);margin:12px 12px}
.aside nav{display:flex;flex-direction:column;gap:4px}.aside nav a{display:block;color:var(--muted);font-size:14px;padding:10px 13px;border-radius:10px}.aside nav a.active{background:#e5eafa;color:var(--navy);font-weight:700}.aside nav a:hover{background:#e9edf7;text-decoration:none}
.content{min-width:0;background:#fff;border:1px solid var(--border);border-radius:18px;padding:44px clamp(22px,5vw,64px);box-shadow:0 12px 40px rgba(9,23,53,.035)}
.eyebrow{color:var(--blue);font-size:12px;font-weight:750;letter-spacing:.12em;text-transform:uppercase}.content h1{font-size:clamp(27px,4vw,39px);line-height:1.17;color:var(--navy);letter-spacing:-.035em;margin:12px 0 26px}
.content h2{font-size:23px;color:var(--navy);letter-spacing:-.025em;margin:39px 0 12px;padding-top:8px;border-top:1px solid #eff1f6}.content h3{font-size:18px;color:var(--navy);margin-top:28px}
.content p,.content li{font-size:15px}.content p{margin:12px 0}.content ul,.content ol{padding-left:25px}.content li{padding-left:3px;margin:6px 0}
.content code{background:#f0f3fa;padding:2px 5px;border-radius:5px;font-size:.87em;color:#274291}.content pre{background:#091735;color:#f1f4fe;border-radius:10px;padding:18px 20px;overflow-x:auto;line-height:1.55}.content pre code{color:inherit;background:none;padding:0}
.table-wrap{overflow-x:auto;margin:22px 0}.content table{border-collapse:collapse;width:100%;font-size:14px}.content th,.content td{padding:12px 14px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}.content th{background:#f5f7fc;color:var(--navy);font-weight:700}.content blockquote{margin:20px 0;border-left:3px solid var(--blue);padding:8px 16px;background:#f5f7fc}
.meta{font-size:13px;color:var(--muted);margin-top:30px}.api-call{margin-top:24px;border:1px solid var(--border);border-radius:12px;background:var(--bg);padding:13px 17px;font-size:13px}
@media(max-width:800px){.shell{display:block;padding:16px}.aside{position:static;margin-bottom:20px}.aside nav{flex-direction:row;flex-wrap:wrap}.aside h2{display:none}.content{padding:25px 20px}.header{padding:12px 18px}.header .back{font-size:12px}}
"""


def page_html(page: str, source: Path, label: str) -> str:
    body = markdown_body(source.read_text(encoding="utf-8"))
    navigation = "\n".join(
        f'<a href="{"index" if key == "index" else key}.html"'
        f'{" class=\"active\" aria-current=\"page\"" if key == page else ""}>{html.escape(name)}</a>'
        for key, (_, name) in SOURCES.items()
    )
    title = "FormFlow — " + label
    return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#091735">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="/static/documentation/docs.css">
</head>
<body>
<header class="header"><a class="brand" href="/">formflow<span>·</span> AI</a><a class="back" href="/">← Wróć do aplikacji</a></header>
<div class="shell">
<aside class="aside"><h2>Dokumentacja</h2><nav aria-label="Sekcje dokumentacji">{navigation}</nav></aside>
<main class="content"><div class="eyebrow">HackNation 2026 · FormFlow v1.4</div>{body}
<div class="api-call">Schemat REST API (OpenAPI JSON): <a href="/api/openapi.json">/api/openapi.json</a></div>
<p class="meta">Dokumentacja wygenerowana z plików Markdown w repozytorium. Bez JavaScript i zewnętrznych zasobów.</p>
</main>
</div>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    missing: list[str] = []
    css_target = OUT / "docs.css"
    if options.check:
        if not css_target.exists() or css_target.read_text(encoding="utf-8") != CSS:
            missing.append(str(css_target.relative_to(ROOT)))
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        css_target.write_text(CSS, encoding="utf-8")
    for key, (path, label) in SOURCES.items():
        target = OUT / ("index.html" if key == "index" else f"{key}.html")
        rendered = page_html(key, ROOT / path, label)
        if options.check:
            if not target.exists() or target.read_text(encoding="utf-8") != rendered:
                missing.append(str(target.relative_to(ROOT)))
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            print(target.relative_to(ROOT))
    if missing:
        raise SystemExit("Outdated docs: " + ", ".join(missing))


if __name__ == "__main__":
    main()

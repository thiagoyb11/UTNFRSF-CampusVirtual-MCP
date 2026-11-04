"""Convierte HTML publicado en Moodle a Markdown acotado, sin red ni ejecución."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlsplit

from utnfrsf_campus_mcp.models import ContentLink
from utnfrsf_campus_mcp.parsers.resources import clean_link

MAX_BLOCK_CHARS = 20_000
# Genially se usa como menú de portada; sus botones repiten secciones del propio campus.
IGNORED_EMBED_HOSTS = ("genially.com",)
_SKIPPED = {"script", "style", "noscript", "template", "form", "button", "select", "textarea"}
_BLOCKS = {"p", "div", "section", "article", "blockquote", "center", "ul", "ol", "table"}
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_VOID = {"br", "hr", "img", "input", "meta", "link", "source", "track", "wbr", "col", "embed"}


@dataclass
class ParsedContent:
    text: str
    links: list[ContentLink]
    embeds: list[str]
    truncated: bool


@dataclass
class _Table:
    rows: list[list[str]] = field(default_factory=list)
    cell: list[str] | None = None


class _Markdown(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._source_url = source_url
        self._out: list[str] = []
        self._skip = 0
        self._link: tuple[str | None, list[str]] | None = None
        self._table: _Table | None = None
        self._lists: list[list[int | None]] = []
        self.links: list[ContentLink] = []
        self.embeds: list[str] = []

    def _write(self, text: str) -> None:
        if self._link is not None:
            self._link[1].append(text)
        elif self._table is not None:
            if self._table.cell is not None:
                self._table.cell.append(text)
        else:
            self._out.append(text)

    def _break(self) -> None:
        if self._table is None and self._link is None:
            self._out.append("\n\n")

    def handle_starttag(self, tag, attrs):
        if self._skip:
            if tag in _SKIPPED:
                self._skip += 1
            return
        values = dict(attrs)
        if tag in _SKIPPED:
            self._skip = 1
        elif tag in ("iframe", "object", "embed"):
            self._embed(values.get("src") or values.get("data"))
        elif tag in _HEADINGS:
            self._break()
            self._write("#" * int(tag[1]) + " ")
        elif tag == "table" and self._table is None:
            self._break()
            self._table = _Table()
        elif tag == "tr" and self._table is not None:
            self._table.rows.append([])
        elif tag in ("td", "th") and self._table is not None:
            self._table.cell = []
        elif tag in ("ul", "ol"):
            self._lists.append([0 if tag == "ol" else None])
            if len(self._lists) == 1:
                self._break()
        elif tag == "li":
            self._list_item()
        elif tag == "a" and self._link is None:
            self._link = (clean_link(values.get("href"), self._source_url), [])
        elif tag == "br":
            self._write(" " if self._table is not None else "\n")
        elif tag == "img" and values.get("alt"):
            self._write(f"[imagen: {values['alt'].strip()}]")
        elif tag in ("strong", "b"):
            self._write("**")
        elif tag in ("em", "i"):
            self._write("*")
        elif tag in _BLOCKS:
            self._break()

    def handle_endtag(self, tag):
        if self._skip:
            if tag in _SKIPPED:
                self._skip -= 1
            return
        if tag in _HEADINGS or tag in _BLOCKS - {"table", "ul", "ol"}:
            self._break()
        elif tag in ("td", "th") and self._table is not None:
            self._close_cell()
        elif tag == "table" and self._table is not None:
            self._close_table()
        elif tag in ("ul", "ol") and self._lists:
            self._lists.pop()
            if not self._lists:
                self._break()
        elif tag == "a" and self._link is not None:
            self._close_link()
        elif tag in ("strong", "b"):
            self._write("**")
        elif tag in ("em", "i"):
            self._write("*")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self._skip:
            self._write(re.sub(r"\s+", " ", data.replace("\xa0", " ")))

    def _embed(self, raw: str | None) -> None:
        url = clean_link(raw, self._source_url)
        host = (urlsplit(url).hostname or "") if url else ""
        ignored = any(host == h or host.endswith("." + h) for h in IGNORED_EMBED_HOSTS)
        if host and not ignored and host not in self.embeds:
            self.embeds.append(host)

    def _list_item(self) -> None:
        if not self._lists:
            self._write("\n- ")
            return
        counter = self._lists[-1]
        marker = "- "
        if counter[0] is not None:
            counter[0] += 1
            marker = f"{counter[0]}. "
        self._write("\n" + "  " * (len(self._lists) - 1) + marker)

    def _close_link(self) -> None:
        url, parts = self._link
        self._link = None
        name = " ".join("".join(parts).split())
        if url and name:
            self._write(f"[{name}]({url})")
            self.links.append(ContentLink(name=name, url=url))
        elif name:
            self._write(name)

    def _close_cell(self) -> None:
        table = self._table
        text = " ".join("".join(table.cell or []).split()).replace("|", "\\|")
        table.cell = None
        if table.rows:
            table.rows[-1].append(text)

    def _close_table(self) -> None:
        rows = [row for row in self._table.rows if any(row)]
        self._table = None
        if not rows:
            return
        width = max(len(row) for row in rows)
        rows = [row + [""] * (width - len(row)) for row in rows]
        lines = [f"| {' | '.join(rows[0])} |", f"| {' | '.join(['---'] * width)} |"]
        lines += [f"| {' | '.join(row)} |" for row in rows[1:]]
        self._out.append("\n\n" + "\n".join(lines) + "\n\n")

    def result(self) -> str:
        return "".join(self._out)


def _tidy(text: str) -> str:
    lines = [" ".join(line.split(" ")).rstrip() for line in text.split("\n")]
    blocks: list[str] = []
    for line in lines:
        if line.strip() or (blocks and blocks[-1]):
            blocks.append(line if line.startswith((" ", "|")) else line.strip())
    return "\n".join(blocks).replace("****", "").strip()


def html_to_markdown(html: str, source_url: str, max_chars: int = MAX_BLOCK_CHARS) -> ParsedContent:
    """Conserva títulos, listas, tablas y enlaces; descarta scripts, estilos y formularios."""
    parser = _Markdown(source_url)
    parser.feed(html)
    parser.close()
    text = _tidy(parser.result())
    truncated = len(text) > max_chars
    return ParsedContent(text[:max_chars], parser.links, parser.embeds, truncated)

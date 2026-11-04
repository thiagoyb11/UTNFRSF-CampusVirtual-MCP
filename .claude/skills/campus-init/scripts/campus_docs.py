#!/usr/bin/env python3
"""Extrae texto de documentos descargados y limpia temporales, solo con biblioteca estándar.

Uso, desde la raíz del repositorio y con `python3 -I`:
    campus_docs.py extract RUTA
    campus_docs.py cleanup RUTA [RUTA ...]
"""

import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

MAX_XML_BYTES = 50 * 1024 * 1024
SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SLIDE = "http://schemas.openxmlformats.org/drawingml/2006/main"
# Formatos de fecha de Excel incorporados y personalizados con día, mes o año.
DATE_FORMAT_IDS = {14, 15, 16, 17, 22}


def read_xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    if archive.getinfo(name).file_size > MAX_XML_BYTES:
        raise ValueError(f"{name} supera el límite de lectura")
    return ET.fromstring(archive.read(name))


def text_of(node: ET.Element, namespace: str) -> str:
    return "".join(item.text or "" for item in node.iter(f"{{{namespace}}}t"))


def date_styles(archive: zipfile.ZipFile) -> set[int]:
    """Índices de estilo de celda con formato de fecha; un número no es una fecha por su valor."""
    if "xl/styles.xml" not in archive.namelist():
        return set()
    root = read_xml(archive, "xl/styles.xml")
    custom = {
        int(item.get("numFmtId", "0"))
        for item in root.iter(f"{{{SHEET}}}numFmt")
        if re.search(r"[dmy]", re.sub(r'"[^"]*"|\[[^\]]*\]', "", item.get("formatCode", "")), re.I)
    }
    cell_formats = root.find(f"{{{SHEET}}}cellXfs")
    if cell_formats is None:
        return set()
    return {
        index
        for index, item in enumerate(cell_formats)
        if int(item.get("numFmtId", "0")) in DATE_FORMAT_IDS | custom
    }


def extract_xlsx(path: Path) -> str:
    lines = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        strings = []
        if "xl/sharedStrings.xml" in names:
            root = read_xml(archive, "xl/sharedStrings.xml")
            strings = [text_of(item, SHEET) for item in root.findall(f"{{{SHEET}}}si")]
        dates = date_styles(archive)
        sheets = [name for name in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
        for name in sorted(sheets, key=lambda item: int(re.findall(r"\d+", item)[-1])):
            lines.append(f"## Hoja {Path(name).stem}")
            for row in read_xml(archive, name).iter(f"{{{SHEET}}}row"):
                cells = []
                for cell in row.findall(f"{{{SHEET}}}c"):
                    value = cell.find(f"{{{SHEET}}}v")
                    if value is None or value.text is None:
                        continue
                    text = value.text
                    if cell.get("t") == "s":
                        text = strings[int(text)]
                    elif int(cell.get("s", "0")) in dates:
                        day = datetime(1899, 12, 30) + timedelta(days=int(float(text)))
                        text = day.strftime("%Y-%m-%d")
                    cells.append(text.strip())
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def extract_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = read_xml(archive, "word/document.xml")
    paragraphs = (text_of(item, WORD) for item in root.iter(f"{{{WORD}}}p"))
    return "\n".join(item for item in paragraphs if item.strip())


def extract_pptx(path: Path) -> str:
    lines = []
    with zipfile.ZipFile(path) as archive:
        slides = [n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        for name in sorted(slides, key=lambda item: int(re.findall(r"\d+", item)[-1])):
            lines.append(f"## {Path(name).stem}")
            root = read_xml(archive, name)
            lines.extend(
                item.text for item in root.iter(f"{{{SLIDE}}}t") if item.text and item.text.strip()
            )
    return "\n".join(lines)


def extract_pdf(path: Path) -> str:
    binary = shutil.which("pdftotext")
    if binary is None:
        raise ValueError("falta pdftotext")
    done = subprocess.run(
        [binary, "-layout", "--", str(path), "-"],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return done.stdout


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".xlsx": extract_xlsx,
    ".docx": extract_docx,
    ".pptx": extract_pptx,
}


def extract(raw: str) -> int:
    path = Path(raw)
    extractor = EXTRACTORS.get(path.suffix.lower())
    if extractor is None:
        print(f"SIN_SOPORTE: {path.suffix or 'sin extensión'}", file=sys.stderr)
        return 3
    try:
        print(extractor(path))
    except (
        ValueError,
        KeyError,
        OSError,
        ET.ParseError,
        zipfile.BadZipFile,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR_EXTRACCION: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


def cleanup(paths: list[str]) -> int:
    """Borra archivos indicados dentro de downloads/ y las carpetas que queden vacías."""
    root = (Path.cwd() / "downloads").resolve()
    status = 0
    for raw in paths:
        link = Path(raw)
        target = link.resolve()
        if link.is_symlink() or root not in target.parents or not target.is_file():
            print(f"RECHAZADO: {raw}", file=sys.stderr)
            status = 1
            continue
        target.unlink()
        print(f"BORRADO: {target}")
        parent = target.parent
        while parent != root and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return status


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "extract":
        return extract(sys.argv[2])
    if len(sys.argv) >= 3 and sys.argv[1] == "cleanup":
        return cleanup(sys.argv[2:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

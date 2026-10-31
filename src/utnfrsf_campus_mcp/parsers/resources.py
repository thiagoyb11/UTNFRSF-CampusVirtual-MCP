"""Normalización pura de enlaces y snapshots del contenido de una asignatura."""

import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit, urlunsplit

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import CourseError
from utnfrsf_campus_mcp.models import CourseLink, CourseSection, UnlinkedActivity
from utnfrsf_campus_mcp.parsers.login import same_origin

_FILE_SUFFIXES = {
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".txt",
    ".csv",
    ".ipynb",
    ".py",
    ".sql",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".mp3",
    ".mp4",
}
_SECRET = re.compile(r"sesskey|token|password|secret|authorization|signature|api[_-]?key", re.I)
_MODULE_PATH = re.compile(r"/mod/([a-z][a-z0-9_]*)/view\.php\Z")


def invalid_resources() -> CourseError:
    return CourseError(
        "RESOURCES_FORMAT_UNSUPPORTED", "No se pudo verificar la estructura del curso."
    )


def integer(value: Any, minimum: int = 0) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value)):
        raise invalid_resources()
    result = int(value)
    if result < minimum:
        raise invalid_resources()
    return result


def clean_link(raw: Any, source_url: str) -> str | None:
    """Devuelve HTTP(S) sin secretos. Los destinos externos se listan, nunca se visitan."""
    if not isinstance(raw, str) or not raw.strip() or raw.strip().startswith("#"):
        return None
    try:
        url = urljoin(source_url, raw.strip())
        parts = urlsplit(url)
        if (
            parts.scheme not in ("http", "https")
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or _SECRET.search(unquote(parts.query))
            or _SECRET.search(unquote(parts.fragment))
        ):
            return None
        # Fuerza validación de puertos incluso en enlaces que solo se devolverán.
        _ = parts.port
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return None


def module_target(url: str) -> tuple[str, int] | None:
    if not same_origin(url, CAMPUS_BASE_URL):
        return None
    parts = urlsplit(url)
    match = _MODULE_PATH.fullmatch(parts.path)
    ids = parse_qs(parts.query).get("id", [])
    if not match or len(ids) != 1 or not re.fullmatch(r"[1-9][0-9]*", ids[0]):
        return None
    return match[1], int(ids[0])


def section_target(raw: Any, course_id: int, source_url: str) -> tuple[int, str] | None:
    url = clean_link(raw, source_url)
    if not url or not same_origin(url, CAMPUS_BASE_URL):
        return None
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    if parts.path != "/course/view.php" or query.get("id") != [str(course_id)]:
        return None
    values = query.get("section", [])
    if len(values) != 1:
        return None
    index = integer(values[0])
    return index, urljoin(
        CAMPUS_BASE_URL,
        "course/view.php?"
        + urlencode(
            {
                "id": course_id,
                "section": index,
            }
        ),
    )


def make_link(
    row: Any,
    source_url: str,
    section_index: int,
    module_id: int | None = None,
    module_type: str | None = None,
) -> CourseLink | None:
    if not isinstance(row, dict):
        raise invalid_resources()
    url = clean_link(row.get("url"), source_url)
    if not url:
        return None
    parts = urlsplit(url)
    target = module_target(url)
    if not same_origin(url, CAMPUS_BASE_URL):
        kind = "external"
    elif (
        "/pluginfile.php/" in parts.path
        or PurePosixPath(unquote(parts.path)).suffix.lower() in _FILE_SUFFIXES
    ):
        kind = "file"
    elif target:
        kind = {"assign": "assignment", "folder": "folder", "resource": "resource"}.get(
            target[0], "activity"
        )
    else:
        kind = "link"
    name = row.get("name")
    return CourseLink(
        name=" ".join(name.split())
        if isinstance(name, str) and name.strip()
        else unquote(PurePosixPath(parts.path).name) or url,
        url=url,
        kind=kind,
        section_index=section_index,
        module_id=module_id,
        module_type=module_type,
        source_url=source_url,
    )


def parse_course_page(
    payload: Any, course_id: int
) -> tuple[str, list[CourseSection], list[CourseLink], list[UnlinkedActivity], list[CourseSection]]:
    if not isinstance(payload, dict) or not payload.get("present"):
        raise invalid_resources()
    if payload.get("access_denied"):
        raise CourseError("RESOURCES_ACCESS_DENIED", "El campus denegó el acceso al curso.")
    if payload.get("truncated") is not False:
        raise CourseError(
            "RESOURCES_LIMIT_EXCEEDED", "El contenido supera el límite de extracción."
        )
    source = clean_link(payload.get("url"), CAMPUS_BASE_URL)
    if not source or not same_origin(source, CAMPUS_BASE_URL):
        raise invalid_resources()
    parts = urlsplit(source)
    if (
        parts.path != "/course/view.php"
        or parse_qs(parts.query).get("id") != [str(course_id)]
        or str(payload.get("course_id")) != str(course_id)
    ):
        raise invalid_resources()
    format_name = payload.get("format")
    if format_name not in ("topics", "onetopic"):
        raise invalid_resources()
    sections, links, unlinked, navigation = [], [], [], []
    rows = payload.get("sections")
    if not isinstance(rows, list) or not rows:
        raise invalid_resources()
    for row in rows:
        index = integer(row["index"])
        sections.append(
            CourseSection(
                index=index,
                id=integer(row["id"], 1) if row.get("id") else None,
                name=row.get("name"),
                url=source,
                visited=True,
            )
        )
        activities, section_links = row.get("activities"), row.get("links")
        if not isinstance(activities, list) or not isinstance(section_links, list):
            raise invalid_resources()
        activity_urls = set()
        for activity in activities:
            module_id = integer(activity.get("id"), 1)
            types = re.findall(r"(?:^|\s)modtype_([a-z0-9_]+)(?=\s|$)", activity.get("classes", ""))
            if len(types) != 1:
                raise invalid_resources()
            module_type = types[0]
            name = activity.get("name") or module_type
            primary = make_link(
                {"name": name, "url": activity.get("url")}, source, index, module_id, module_type
            )
            if primary:
                target = module_target(primary.url)
                if target and target != (module_type, module_id):
                    raise invalid_resources()
                links.append(primary)
                activity_urls.add(primary.url)
            else:
                unlinked.append(
                    UnlinkedActivity(
                        module_id=module_id,
                        module_type=module_type,
                        name=name,
                        section_index=index,
                        availability=activity.get("availability"),
                    )
                )
            if not isinstance(activity.get("links"), list):
                raise invalid_resources()
            for embedded in activity["links"]:
                link = make_link(embedded, source, index, module_id, module_type)
                if link:
                    activity_urls.add(link.url)
                    links.append(link)
        for embedded in section_links:
            link = make_link(embedded, source, index)
            if link and link.url not in activity_urls:
                links.append(link)
    nav = payload.get("navigation")
    if not isinstance(nav, list):
        raise invalid_resources()
    # Las pestañas tienen prioridad sobre la sidebar para respetar disabled.
    disabled = set()
    for row in nav:
        target = section_target(row.get("url"), course_id, source)
        if target and row.get("disabled") is True:
            disabled.add(target[0])
    for row in nav:
        target = section_target(row.get("url"), course_id, source)
        if target:
            index, url = target
            navigation.append(
                CourseSection(
                    index=index, name=row.get("name"), url=url, available=index not in disabled
                )
            )
    return format_name, sections, links, unlinked, navigation

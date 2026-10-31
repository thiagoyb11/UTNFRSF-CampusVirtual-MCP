"""Validación del listado de asignaturas dentro de My courses → Grado."""

from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL
from utnfrsf_campus_mcp.errors import CourseError
from utnfrsf_campus_mcp.models import Course
from utnfrsf_campus_mcp.parsers.login import same_origin

# El href identifica My courses aunque cambie el idioma de la interfaz.
_MY_COURSES = (
    '[data-block="navigation"] li.type_system:has(> p.tree_item > a[href$="/my/courses.php"])'
)
_PENDING_CATEGORIES = (
    'li[data-requires-ajax="true"]:not([data-loaded="true"]):not(.type_course, .type_course *)'
)
DEGREE_COURSES_SCHEMA = {
    "navigation": {"selector": '[data-block="navigation"]', "attr": "data-block"},
    "roots": [{"selector": f"{_MY_COURSES} > p.tree_item > a[href]", "attr": "href"}],
    "groups": [
        {
            "selector": f"{_MY_COURSES} > ul > li",
            "fields": {
                "name": ":scope > p.tree_item > span",
                "requires_ajax": {"selector": "", "attr": "data-requires-ajax"},
                "loaded": {"selector": "", "attr": "data-loaded"},
                "pending": [
                    {"selector": _PENDING_CATEGORIES, "attr": "data-requires-ajax", "limit": 1}
                ],
                "courses": [
                    {
                        "selector": "li.type_course > p.tree_item > a[href]",
                        "limit": 1001,
                        "fields": {
                            "name": {"selector": "", "attr": "title"},
                            "label": "",
                            "url": {"selector": "", "attr": "href"},
                        },
                    }
                ],
            },
        }
    ],
}


def parse_degree_courses(payload: Any) -> list[Course]:
    """Selecciona Grado y valida la extracción nativa sin ejecutar JavaScript propio."""
    if not isinstance(payload, dict) or payload.get("navigation") != "navigation":
        raise _unsupported_navigation()
    roots, groups = payload.get("roots"), payload.get("groups")
    if (
        not isinstance(roots, list)
        or len(roots) != 1
        or not isinstance(roots[0], str)
        or not same_origin(roots[0], CAMPUS_BASE_URL)
        or urlsplit(roots[0]).path != "/my/courses.php"
        or not isinstance(groups, list)
        or not all(isinstance(group, dict) for group in groups)
    ):
        raise _unsupported_navigation()
    # Grado es el nombre académico de la categoría, no una etiqueta traducida de interfaz.
    degree = [
        group
        for group in groups
        if isinstance(group.get("name"), str) and " ".join(group["name"].split()) == "Grado"
    ]
    if len(degree) != 1:
        raise _unsupported_navigation()
    if degree[0].get("pending") != [] or (
        degree[0].get("requires_ajax") == "true" and degree[0].get("loaded") != "true"
    ):
        raise CourseError("COURSES_INCOMPLETE", "La rama Grado tiene contenido pendiente de carga.")
    items = degree[0].get("courses")
    if not isinstance(items, list):
        raise CourseError(
            "COURSES_INCOMPLETE", "No se pudo confirmar el listado completo de Grado."
        )
    if len(items) > 1000:
        raise CourseError("COURSES_LIMIT_EXCEEDED", "Grado supera el límite de 1000 asignaturas.")
    courses: dict[int, Course] = {}
    for item in items:
        if not isinstance(item, dict):
            raise _invalid_course()
        name, raw_url = item.get("name") or item.get("label"), item.get("url")
        if not isinstance(name, str) or not name.strip() or not isinstance(raw_url, str):
            raise _invalid_course()
        url = urljoin(CAMPUS_BASE_URL, raw_url)
        if not same_origin(url, CAMPUS_BASE_URL):
            raise _invalid_course()
        parts = urlsplit(url)
        ids = parse_qs(parts.query).get("id", [])
        if (
            parts.path != "/course/view.php"
            or len(ids) != 1
            or not ids[0].isascii()
            or not ids[0].isdigit()
            or int(ids[0]) <= 0
        ):
            raise _invalid_course()
        course_id = int(ids[0])
        course = Course(
            id=course_id,
            name=" ".join(name.split()),
            url=urljoin(CAMPUS_BASE_URL, "course/view.php?" + urlencode({"id": course_id})),
        )
        if course_id in courses and courses[course_id] != course:
            raise _invalid_course()
        courses[course_id] = course
    return list(courses.values())


def _invalid_course() -> CourseError:
    return CourseError(
        "COURSES_INVALID_COURSE", "Una asignatura no tiene nombre y enlace inequívocos."
    )


def _unsupported_navigation() -> CourseError:
    return CourseError(
        "COURSES_NAVIGATION_UNSUPPORTED",
        "No se identificó una única rama My courses → Grado en la navegación del campus.",
    )

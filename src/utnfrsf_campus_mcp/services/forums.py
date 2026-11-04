"""Lectura de foros de una asignatura; nunca publica, responde ni se suscribe."""

from datetime import UTC, datetime
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from anyio import fail_after
from lightpanda import LightpandaError

from utnfrsf_campus_mcp.browser.forums import DISCUSSION_SCRIPT, FORUM_LIST_SCRIPT
from utnfrsf_campus_mcp.browser.session import CampusSession
from utnfrsf_campus_mcp.config import CAMPUS_BASE_URL, Settings
from utnfrsf_campus_mcp.errors import CourseError
from utnfrsf_campus_mcp.models import ForumDiscussion, ForumDiscussions
from utnfrsf_campus_mcp.parsers.forums import parse_discussions, parse_posts
from utnfrsf_campus_mcp.parsers.resources import invalid_resources
from utnfrsf_campus_mcp.services.resources import ResourceService

QUERY_TIMEOUT_SECONDS = 120


class ForumService:
    def __init__(
        self, settings: Settings, session: CampusSession, resources: ResourceService
    ) -> None:
        self._settings = settings
        self._session = session
        self._resources = resources

    async def _read(self, url: str, script: str) -> dict:
        try:
            with fail_after(QUERY_TIMEOUT_SECONDS):
                async with self._session.acquire() as page:
                    await self._resources.open_page(page, url)
                    data = await page.evaluate(script=script)
                    await self._resources.require_session(page)
        except TimeoutError:
            raise CourseError("RESOURCES_TIMEOUT", "Se agotó el tiempo de consulta.") from None
        except LightpandaError as exc:
            raise self._resources.browser_error(exc) from None
        if not isinstance(data, dict):
            raise invalid_resources()
        if data.get("access_denied"):
            raise CourseError("FORUM_ACCESS_DENIED", "El campus denegó el acceso al foro.")
        return data

    async def list_discussions(self, course_id: int, forum_id: int) -> ForumDiscussions:
        if type(forum_id) is not int or forum_id <= 0:
            raise CourseError("FORUM_INVALID_ID", "Indicá un forum_id entero positivo.")
        course = await self._resources.find_course(course_id)
        url = urljoin(CAMPUS_BASE_URL, f"mod/forum/view.php?id={forum_id}")
        data = await self._read(url, FORUM_LIST_SCRIPT)
        query = parse_qs(urlsplit(str(data.get("url"))).query)
        if (
            data.get("body") != "page-mod-forum-view"
            or str(data.get("course_id")) != str(course_id)
            or query.get("id") != [str(forum_id)]
        ):
            raise CourseError("FORUM_NOT_FOUND", "El módulo no es un foro de la asignatura.")
        rows = data.get("discussions")
        if not rows and data.get("empty") is not True:
            raise invalid_resources()
        warnings = []
        if data.get("paged") or data.get("truncated"):
            warnings.append("FORUM_PAGINATION_PENDING: El foro tiene más discusiones sin leer.")
        discussions = parse_discussions(rows, url, ZoneInfo(self._settings.timezone))
        return ForumDiscussions(
            course=course,
            forum_id=forum_id,
            name=data.get("name"),
            source_url=url,
            fetched_at=datetime.now(UTC),
            total=len(discussions),
            discussions=discussions,
            complete=not warnings,
            warnings=warnings,
        )

    async def get_discussion(self, course_id: int, discussion_id: int) -> ForumDiscussion:
        if type(discussion_id) is not int or discussion_id <= 0:
            raise CourseError("FORUM_INVALID_ID", "Indicá un discussion_id entero positivo.")
        course = await self._resources.find_course(course_id)
        url = urljoin(CAMPUS_BASE_URL, f"mod/forum/discuss.php?d={discussion_id}")
        data = await self._read(url, DISCUSSION_SCRIPT)
        if data.get("body") != "page-mod-forum-discuss" or str(data.get("course_id")) != str(
            course_id
        ):
            raise CourseError("FORUM_NOT_FOUND", "La discusión no es de la asignatura.")
        posts, warnings = parse_posts(data.get("posts"), url)
        if data.get("truncated"):
            warnings.append("FORUM_PAGINATION_PENDING: La discusión tiene más mensajes sin leer.")
        return ForumDiscussion(
            course=course,
            discussion_id=discussion_id,
            title=data.get("title"),
            source_url=url,
            fetched_at=datetime.now(UTC),
            total=len(posts),
            posts=posts,
            complete=not warnings,
            warnings=warnings,
        )

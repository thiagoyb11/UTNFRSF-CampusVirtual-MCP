"""Normaliza snapshots de foros sin red; las fechas conservan su zona."""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from utnfrsf_campus_mcp.models import ContentLink, ForumDiscussionSummary, ForumPost
from utnfrsf_campus_mcp.parsers.content import html_to_markdown
from utnfrsf_campus_mcp.parsers.resources import clean_link, integer, invalid_resources


# Moodle publica las fechas de la lista como timestamp Unix; se convierten a la zona del campus.
def _instant(raw: Any, zone: ZoneInfo) -> datetime | None:
    if raw in (None, ""):
        return None
    return datetime.fromtimestamp(integer(raw, 1), UTC).astimezone(zone)


def parse_discussions(rows: Any, source_url: str, zone: ZoneInfo) -> list[ForumDiscussionSummary]:
    if not isinstance(rows, list):
        raise invalid_resources()
    result = []
    for row in rows:
        # El enlace debe ser discuss.php?d=<id> con el mismo id de la fila; si no coincide,
        # la página no tiene la estructura esperada y se falla en lugar de adivinar.
        url = clean_link(row.get("url"), source_url)
        identifier = integer(row.get("id"), 1)
        parts = urlsplit(url or "")
        if (
            url is None
            or parts.path != "/mod/forum/discuss.php"
            or parse_qs(parts.query).get("d") != [str(identifier)]
            or not row.get("title")
        ):
            raise invalid_resources()
        # La cantidad de respuestas es opcional: si no es un número, se informa como desconocida.
        replies = str(row.get("replies") or "")
        result.append(
            ForumDiscussionSummary(
                id=identifier,
                title=row["title"],
                url=url,
                author=row.get("author"),
                group=row.get("group"),
                started_at=_instant(row.get("started"), zone),
                last_post_at=_instant(row.get("last_post"), zone),
                replies=int(replies) if replies.isdigit() else None,
            )
        )
    return result


def parse_posts(rows: Any, source_url: str) -> tuple[list[ForumPost], list[str]]:
    if not isinstance(rows, list) or not rows:
        raise invalid_resources()
    posts: list[ForumPost] = []
    warnings: list[str] = []
    for row in rows:
        # Todo mensaje debe traer cuerpo; la fecha viene del atributo datetime, en ISO 8601.
        if row.get("html") is None:
            raise invalid_resources()
        raw_date = row.get("posted_at")
        try:
            posted_at = datetime.fromisoformat(raw_date) if raw_date else None
        except (TypeError, ValueError):
            raise invalid_resources() from None
        # El cuerpo pasa a Markdown; los recortes y embebidos omitidos se informan como warnings.
        parsed = html_to_markdown(row["html"], source_url)
        if parsed.truncated:
            warnings.append("CONTENT_TRUNCATED: Un mensaje superó el límite de texto.")
        if parsed.embeds:
            warnings.append(
                "CONTENT_EMBEDS_OMITTED: Hay contenido embebido de " + ", ".join(parsed.embeds)
            )
        # Adjuntos: solo enlaces limpios (sin secretos) y con nombre visible.
        attachments = []
        for item in row.get("attachments") or []:
            url = clean_link(item.get("url"), source_url)
            if url and item.get("name"):
                attachments.append(ContentLink(name=item["name"], url=url))
        parent = row.get("parent_id")
        posts.append(
            ForumPost(
                id=integer(row.get("id"), 1),
                parent_id=integer(parent, 1) if parent else None,
                subject=row.get("subject"),
                author=row.get("author"),
                posted_at=posted_at,
                text=parsed.text,
                links=parsed.links,
                attachments=attachments,
                truncated=parsed.truncated,
            )
        )
    # dict.fromkeys elimina warnings repetidos conservando el orden de aparición.
    return posts, list(dict.fromkeys(warnings))

"""Lectura acotada del DOM y de páginas de recursos en la sesión Lightpanda."""

import json

from lightpanda import AsyncSession

# Solo se lee contenido académico y navegación de secciones. Sin valores de formularios,
# identidad ni configuración privada de Moodle. No se pulsan controles de actividades.
COURSE_CONTENT_SCRIPT = r"""(() => {
    const root = document.querySelector('#region-main .course-content');
    const text = el => el?.textContent?.trim() || null;
    let truncated = false;
    const bounded = nodes => {
        const rows = [...nodes];
        if (rows.length > 5000) truncated = true;
        return rows.slice(0, 5000);
    };
    const links = el => bounded(el.querySelectorAll('a[href]')).map(a => ({
        name: text(a), url: a.getAttribute('href')
    }));
    const sections = root ? bounded(root.querySelectorAll('li.section[data-sectionid]')).map(s => ({
        index: s.getAttribute('data-sectionid'), id: s.getAttribute('data-id'),
        name: s.getAttribute('data-sectionname') || text(s.querySelector('.sectionname')),
        links: links(s),
        activities: bounded(s.querySelectorAll('li.activity[data-id]')).map(a => ({
            id: a.getAttribute('data-id'), classes: a.className,
            name: a.querySelector('[data-region="activity-card"]')
                ?.getAttribute('data-activityname') || text(a.querySelector('.instancename')),
            url: a.querySelector('a.aalink[href]')?.getAttribute('href') || null,
            links: links(a),
            availability: text(a.querySelector(
                '.availabilityinfo, [data-region="availabilityinfo"]'))
        }))
    })) : [];
    const current = new URL(location.href).searchParams.get('id');
    const courseNodes = [...document.querySelectorAll('[data-block="navigation"] li.type_course')]
        .filter(li => {
            const a = li.querySelector(':scope > p.tree_item > a[href]');
            if (!a) return false;
            const u = new URL(a.href, location.href);
            return u.origin === location.origin && u.pathname === '/course/view.php' &&
                u.searchParams.get('id') === current;
        });
    const tabs = [...document.querySelectorAll('ul.format_onetopic-tabs a.nav-link[href]')];
    const sidebar = courseNodes.flatMap(li =>
        [...li.querySelectorAll('li.type_structure > p.tree_item > a[href]')]);
    const navigation = bounded([...tabs, ...sidebar]).map(a => ({
        url: a.getAttribute('href'), name: text(a),
        disabled: !!a.closest('.disabled, [aria-disabled="true"]'),
        tab: tabs.includes(a)
    }));
    return {url: location.href, course_id: current,
        format: document.body.classList.contains('format-topics') ? 'topics' :
            document.body.classList.contains('format-onetopic') ? 'onetopic' : null,
        sections, navigation, truncated, present: !!root,
        access_denied: !!document.querySelector(
            '#region-main .alert-danger, #region-main .errorbox')};
})()"""

# HTML publicado en una sección, sin controles de edición. __SECTION__ se reemplaza por un entero.
SECTION_CONTENT_SCRIPT = r"""(() => {
    const root = document.querySelector('#region-main .course-content');
    const section = root?.querySelector('li.section[data-sectionid="__SECTION__"]');
    const text = el => el?.textContent?.trim() || null;
    const limit = 300000;
    const html = el => el ? el.innerHTML.slice(0, limit) : null;
    const activities = section ? [...section.querySelectorAll('li.activity[data-id]')] : [];
    return {url: location.href, course_id: new URL(location.href).searchParams.get('id'),
        present: !!root, found: !!section,
        name: section?.getAttribute('data-sectionname') ||
            text(section?.querySelector('.sectionname')),
        summary: html(section?.querySelector('.summarytext')),
        activities: activities.slice(0, 500).map(a => ({
            id: a.getAttribute('data-id'), classes: a.className,
            name: a.querySelector('[data-region="activity-card"]')
                ?.getAttribute('data-activityname') || text(a.querySelector('.instancename')),
            html: html(a.querySelector('.activity-altcontent')),
            availability: text(a.querySelector(
                '.availabilityinfo, [data-region="availabilityinfo"]'))
        })),
        truncated: activities.length > 500,
        access_denied: !!document.querySelector(
            '#region-main .alert-danger, #region-main .errorbox')};
})()"""

# Solo el cuerpo publicado de mod/page, sin navegación ni bloques laterales.
PAGE_CONTENT_SCRIPT = r"""(() => {
    const main = document.querySelector('#region-main');
    const box = main?.querySelector('.box.generalbox');
    return {url: location.href, body: document.body.id, course_id: M.cfg.courseId,
        name: main?.querySelector('h2')?.textContent?.trim() || null,
        html: box ? box.innerHTML.slice(0, 500000) : null,
        access_denied: !!main?.querySelector('.alert-danger, .errorbox')};
})()"""

# GET de páginas conocidas: no sigue redirecciones (tampoco a un origen externo),
# no descarga binarios ni ejecuta el HTML recibido. forceview es el parámetro de lectura
# de mod/resource/view.php de Moodle para obtener el enlace incluso en modo download.
_MODULE_CONTENT_SCRIPT = r"""return await (async () => {
    const url = new URL(__URL__, location.href);
    if (url.origin !== location.origin) return {error: 'RESOURCES_ACCESS_DENIED'};
    let response;
    try {
        response = await fetch(url.href, {credentials: 'same-origin', redirect: 'error'});
    } catch (_) { return {error: 'RESOURCES_REDIRECT_OR_FETCH_FAILED'}; }
    if (response.status === 429) return {error: 'RESOURCES_RATE_LIMITED'};
    if ([401, 403].includes(response.status)) return {error: 'RESOURCES_ACCESS_DENIED'};
    if (!response.ok) return {error: 'RESOURCES_HTTP_ERROR'};
    const type = response.headers.get('content-type') || '';
    if (!type.toLowerCase().includes('text/html')) {
        await response.body?.cancel();
        return {error: 'RESOURCES_UNEXPECTED_CONTENT'};
    }
    const html = await response.text();
    if (html.length > 2000000) return {error: 'RESOURCES_LIMIT_EXCEEDED'};
    const doc = new DOMParser().parseFromString(html, 'text/html');
    if (doc.querySelector('input[name="password"], body.notloggedin')) {
        return {error: 'RESOURCES_SESSION_EXPIRED'};
    }
    const main = doc.querySelector('#region-main');
    if (!main) return {error: 'RESOURCES_FORMAT_UNSUPPORTED'};
    if (main.querySelector('.alert-danger, .errorbox')) {
        return {error: 'RESOURCES_ACCESS_DENIED'};
    }
    // Excluye navegación de otros módulos, formularios y archivos de entregas personales.
    const scope = url.pathname === '/mod/assign/view.php' ?
        [...main.querySelectorAll('#intro, .activity-description')] : [main];
    const nodes = scope.flatMap(el => [...el.querySelectorAll(
        'a[href], iframe[src], object[data], embed[src]')]).filter(el =>
            !el.closest(
                'form, .activity-navigation, .submissionstatustable, .submissionsummarytable'));
    return {links: nodes.slice(0, 5000).map(el => ({
        name: el.textContent?.trim() || el.getAttribute('title'),
        url: el.getAttribute('href') || el.getAttribute('src') || el.getAttribute('data')
    })), truncated: nodes.length > 5000};
})()"""


async def read_module_links(page: AsyncSession, url: str) -> object:
    """Lee solo una URL interna validada por el servicio; no expone JS al cliente MCP."""
    return await page.evaluate(script=_MODULE_CONTENT_SCRIPT.replace("__URL__", json.dumps(url)))

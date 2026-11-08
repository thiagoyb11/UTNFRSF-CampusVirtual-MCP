"""Snapshots acotados de foros; no pulsan controles ni leen formularios."""

# Lista de discusiones de mod/forum/view.php. Por cada fila devuelve id, título, enlace,
# autor, grupo, timestamps de inicio y último mensaje, y cantidad de respuestas.
# Limita a 500 filas (truncated) e informa si hay paginación, para no dar el foro por completo.
FORUM_LIST_SCRIPT = r"""(() => {
    const main = document.querySelector('#region-main');
    const text = el => el?.textContent?.trim() || null;
    const rows = [...(main?.querySelectorAll('tr.discussion[data-discussionid]') || [])];
    return {url: location.href, body: document.body.id, course_id: M.cfg.courseId,
        name: text(main?.querySelector('h2, h3')),
        empty: !!main?.querySelector('.forumnodiscuss'),
        paged: !!main?.querySelector('.pagination, nav[aria-label*="age"]'),
        truncated: rows.length > 500,
        discussions: rows.slice(0, 500).map(row => {
            const link = row.querySelector('th.topic a[href*="discuss.php"]');
            const times = [...row.querySelectorAll('time[data-timestamp]')];
            return {id: row.getAttribute('data-discussionid'), title: text(link),
                url: link?.getAttribute('href') || null,
                author: text(row.querySelector('td.author .author-info .text-truncate')) ||
                    text(row.querySelector('td.author a')),
                group: text(row.querySelector('td.group')),
                started: times[0]?.getAttribute('data-timestamp') || null,
                last_post: times[1]?.getAttribute('data-timestamp') || null,
                replies: text(row.querySelector('td:nth-last-child(2)'))};
        }),
        access_denied: !!main?.querySelector('.alert-danger, .errorbox')};
})()"""

# Mensajes de mod/forum/discuss.php: id, padre (para reconstruir el hilo), asunto, autor,
# fecha, HTML del cuerpo y adjuntos que no están dentro del cuerpo.
# Cada post anida sus respuestas: se lee solo su primer contenedor propio.
DISCUSSION_SCRIPT = r"""(() => {
    const main = document.querySelector('#region-main');
    const text = el => el?.textContent?.trim() || null;
    const posts = [...(main?.querySelectorAll('article.forum-post-container[data-post-id]') || [])];
    return {url: location.href, body: document.body.id, course_id: M.cfg.courseId,
        title: text(main?.querySelector('h3.discussionname, h2, h3')),
        truncated: posts.length > 500,
        posts: posts.slice(0, 500).map(post => {
            const own = post.querySelector(':scope > div');
            const parent = post.parentElement
                ?.closest('article.forum-post-container[data-post-id]');
            const content = own?.querySelector('.post-content-container');
            return {id: post.getAttribute('data-post-id'),
                parent_id: parent?.getAttribute('data-post-id') || null,
                subject: text(own?.querySelector('header h3, header h4')),
                author: text(own?.querySelector('header a')),
                posted_at: own?.querySelector('header time[datetime]')?.getAttribute('datetime')
                    || null,
                html: content ? content.innerHTML.slice(0, 300000) : null,
                attachments: [...(own?.querySelectorAll('a[href*="pluginfile.php"]') || [])]
                    .filter(a => !content?.contains(a))
                    .map(a => ({name: text(a), url: a.getAttribute('href')}))};
        }),
        access_denied: !!main?.querySelector('.alert-danger, .errorbox')};
})()"""

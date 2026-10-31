"""Snapshot acotado del estado y de acciones observadas de una tarea Moodle."""

SUBMISSION_STATE_SCRIPT = r"""(() => {
    const main = document.querySelector('#region-main');
    if (!main) return null;
    const forms = [...main.querySelectorAll('form')].filter(f =>
        new URL(f.action, location.href).pathname === '/mod/assign/view.php');
    const actions = forms.filter(f => f.method.toLowerCase() === 'get').map(f => {
        const action = f.elements.namedItem('action')?.value;
        if (!['editsubmission', 'submit', 'submitforgrading'].includes(action)) return null;
        const u = new URL(f.action, location.href);
        for (const input of [...f.elements]) {
            if (input.name && input.type === 'hidden') u.searchParams.set(input.name, input.value);
        }
        return {action, url: u.href};
    }).filter(Boolean);
    const rows = [...main.querySelectorAll('.submissionstatustable tr, table.generaltable tr')]
        .slice(0, 4).map(row => ({
            classes: [...row.querySelectorAll('td')].map(e => e.className).join(' '),
            text: row.textContent.trim()
        }));
    const files = [...main.querySelectorAll('a[href]')].filter(a =>
        new URL(a.href).pathname.includes('/assignsubmission_file/')).map(a => ({
            name: a.textContent.trim(), url: a.href
        }));
    return {url: location.href, body: document.body.id, course_id: M.cfg.courseId,
        account_id: M.cfg.userId, name: main.querySelector('h2')?.textContent.trim(),
        actions, rows, files,
        error: !!main.querySelector('.errorbox, .alert-danger')};
})()"""

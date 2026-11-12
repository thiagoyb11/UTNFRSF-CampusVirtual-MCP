"""Snapshot acotado del estado y de acciones observadas de una tarea Moodle."""

# Script que se ejecuta dentro de la página de una tarea (mod/assign/view.php).
# Devuelve solo lo necesario para decidir el flujo de entrega:
# - actions: botones GET de Moodle (editar, enviar, enviar para calificar) con su URL completa.
# - rows: las primeras filas de la tabla de estado, para leer si hay borrador o entrega.
# - files: archivos ya adjuntos a la entrega del alumno.
# - course_id y account_id: para confirmar materia y cuenta antes de escribir.
# No lee valores de formularios ni datos personales fuera de esa tabla.
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


# Script de solo lectura del bloque de devolución (div.feedback) de una tarea, observado el
# 9 de noviembre de 2026: div.feedback > div.feedbacktable > table > tr con th (etiqueta
# traducida) y td (valor). No usa las etiquetas para decidir; devuelve por fila:
# - grader: la celda enlaza un perfil /user/view.php (fila "Calificado por").
# - plugins: clases summary_assignfeedback_<plugin>_<id> de la celda (comentarios, etc.).
# - links: enlaces de la celda, para archivos devueltos y vistas completas.
# - rubric: la celda contiene una guía o rúbrica de calificación avanzada.
# El texto conserva saltos de párrafo y omite las iniciales del avatar del docente.
FEEDBACK_SCRIPT = r"""(() => {
    const main = document.querySelector('#region-main');
    if (!main) return null;
    const block = 'P DIV LI TR H1 H2 H3 H4 H5 H6 TABLE UL OL BLOCKQUOTE PRE'.split(' ');
    const text = root => {
        const parts = [];
        const walk = node => {
            if (node.nodeType === 3) { parts.push(node.data); return; }
            if (node.nodeType !== 1) return;
            if (['SCRIPT', 'STYLE'].includes(node.tagName)) return;
            if (node.classList.contains('userinitials')) return;
            if (node.tagName === 'BR') { parts.push('\n'); return; }
            const isBlock = block.includes(node.tagName);
            if (isBlock) parts.push('\n');
            for (const child of node.childNodes) walk(child);
            if (isBlock) parts.push('\n');
        };
        walk(root);
        return parts.join('').split('\n').map(l => l.replace(/\s+/g, ' ').trim())
            .filter(Boolean).join('\n');
    };
    const feedback = main.querySelector('.feedback');
    const rows = feedback ? [...feedback.querySelectorAll('.feedbacktable tr')].map(tr => {
        const th = tr.querySelector('th');
        const td = tr.querySelector('td');
        if (!td) return null;
        const links = [...td.querySelectorAll('a[href]')].map(a => ({
            name: text(a), url: a.href
        }));
        return {
            label: th ? text(th) : '',
            text: text(td),
            grader: links.some(l => new URL(l.url).pathname === '/user/view.php'),
            plugins: [...td.querySelectorAll('[class*="summary_assignfeedback_"]')]
                .flatMap(el => [...el.classList])
                .map(c => /^summary_assignfeedback_([a-z0-9]+)_\d+$/.exec(c)?.[1])
                .filter(Boolean),
            links,
            rubric: !!td.querySelector('[class*="gradingform_"]'),
        };
    }).filter(Boolean) : [];
    return {url: location.href, present: !!feedback,
        timezone: globalThis.M?.cfg?.usertimezone, rows};
})()"""

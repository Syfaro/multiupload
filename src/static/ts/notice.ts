const notices = Array.from(document.querySelectorAll('.notices button.close'));

async function dismissNotice(ev) {
    const alert = ev.target.parentNode.parentNode as HTMLDivElement;
    const span = alert.querySelector('span[data-id]') as HTMLSpanElement;

    if (!span) return;

    const id = span.dataset.id;

    await fetch(Multiupload.endpoints.notice.dismiss, {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': Multiupload.csrf,
        },
        body: `id=${id}`,
    });

    alert.classList.add('d-none');
}

notices.forEach(notice => notice.addEventListener('click', dismissNotice));

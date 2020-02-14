class Notice {
    constructor(selector = '.notices button.close') {
        this.notices = Array.from(document.querySelectorAll(selector));
        this.notices.forEach(notice => notice.addEventListener('click', Notice.noticeDismissed));
    }
    static async noticeDismissed(ev) {
        ev.preventDefault();
        const alert = ev.target.parentNode.parentNode;
        const span = alert.querySelector('span[data-id]');
        if (!span)
            return;
        const id = span.dataset.id;
        if (!id)
            return;
        await Notice.dismissNotification(id);
        if (!alert.parentNode)
            return;
        alert.parentNode.removeChild(alert);
    }
    static async dismissNotification(id) {
        return fetch(Multiupload.endpoints.notice.dismiss, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': Multiupload.csrf,
            },
            body: `id=${id}`,
        });
    }
}
new Notice();
//# sourceMappingURL=notice.js.map
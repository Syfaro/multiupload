if (Multiupload.sentry) {
    Raven.config(Multiupload.sentry).install();

    if (Multiupload.release) {
        Raven.setRelease(Multiupload.release);

        window.addEventListener('load', () => {
            document.querySelector('.revision').classList.remove('d-none');
            document.querySelector('.revision a').style.color = '#' + Multiupload.release.slice(-6);
        });
    }

    if (Multiupload.user) Raven.setUserContext(Multiupload.user);
}

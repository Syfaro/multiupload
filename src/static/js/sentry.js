if (Multiupload.release) {
     window.addEventListener('load', () => {
            document.querySelector('.revision').classList.remove('d-none');
            document.querySelector('.revision a').style.color = '#' + Multiupload.release.slice(-6);
        });
    }

if (Multiupload.sentry) {
    Raven.config(Multiupload.sentry).install();

    if (Multiupload.user) Raven.setUserContext(Multiupload.user);
}

if (Multiupload.release && Multiupload.sentry) {
    Raven.setRelease(Multiupload.release);
}

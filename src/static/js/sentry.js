Raven.config(Multiupload.sentry).install();

if (Multiupload.release) {
    Raven.setRelease(Multiupload.release);

    window.addEventListener('load', () => {
        document.querySelector('.revision').classList.remove('d-none');
        document.querySelector('.revision a').style.color = '#' + Multiupload.release.slice(-6);
    });
}

const userID = document.querySelector('meta[name="user-id"]');
const userEmail = document.querySelector('meta[name="user-email"]');

Raven.setUserContext({
    email: userEmail ? userEmail.content : null,
    id: userID ? userID.content : null,
});

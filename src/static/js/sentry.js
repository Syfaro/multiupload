Raven.config('https://2af2d6d7acf04c6fb581e25a8601c15e@sentry.io/1187790').install();

const release = document.querySelector('meta[name="release"]');
if (release) {
    const content = release.content;

    Raven.setRelease(content);

    window.addEventListener('load', () => {
        document.querySelector('.revision').classList.remove('d-none');
        document.querySelector('.revision a').style.color = '#' + content.slice(-6);
    });
}

const userID = document.querySelector('meta[name="user-id"]');
const userEmail = document.querySelector('meta[name="user-email"]');

Raven.setUserContext({
    email: userEmail ? userEmail.content : null,
    id: userID ? userID.content : null,
});

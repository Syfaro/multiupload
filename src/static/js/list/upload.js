const submits = Array.from(document.querySelectorAll('.submit-submission'));

const clickSubmit = ev => {
    ev.preventDefault();

    if (ev.target.classList.contains('disabled')) return;
    const id = ev.target.parentNode.querySelector('input[name="id"]').value;

    ev.target.classList.add('disabled');

    const frame = document.createElement('iframe');
    frame.src = `/upload/review/${id}`;
    frame.style.height = 0;
    frame.style.width = 0;
    frame.style.display = 'none';
    let loaded = false;
    frame.addEventListener('load', () => {
        const content = frame.contentWindow;

        if (loaded) {
            document.body = content.document.body;
            return;
        }
        loaded = true;

        const submit = content.document.querySelector('button[type="submit"].btn-primary');
        submit.click();
    });
    document.body.appendChild(frame);
};

submits.forEach(submit => {
    submit.addEventListener('click', clickSubmit);
});

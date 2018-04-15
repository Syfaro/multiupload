declare const Raven;

const uploadBody = document.querySelector('#uploadModal .modal-body') as HTMLDivElement;
const uploadClose = document.querySelector('#uploadModal button') as HTMLButtonElement;

function uploadWithEvents(id: number) {
    const source = new EventSource(`/upload/art/saved?id=${id}`);
    let hadError = false;
    let count = 0;
    let uploaded = 0;

    uploadBody.innerHTML = '';

    const p = document.createElement('p');
    uploadBody.appendChild(p);

    const progress = document.createElement('div');
    progress.classList.add('progress');
    uploadBody.appendChild(progress);

    const bar = document.createElement('div');
    bar.classList.add('progress-bar', 'progress-bar-striped', 'bg-info');

    progress.appendChild(bar);

    const div = document.createElement('div');
    const ul = document.createElement('ul');
    div.appendChild(ul);
    uploadBody.appendChild(div);

    function updateProgress() {
        bar.style.width = `${Math.round(uploaded / count * 100)}%`;
    }

    function setError(message?: string) {
        hadError = true;

        bar.classList.remove('bg-info');
        bar.classList.add('bg-warning');

        if (message) {
            const e = document.createElement('div');
            e.innerHTML = message;
            uploadBody.appendChild(e);
        }
    }

    source.addEventListener('count', ev => {
        count = parseFloat((ev as MessageEvent).data);
        p.innerHTML = `Creating ${count} submissions.`;

        bar.classList.add('progress-bar-animated');
    });

    source.addEventListener('upload', ev => {
        uploaded++;

        const data = JSON.parse((ev as MessageEvent).data);

        const li = document.createElement('li');
        const a = document.createElement('a');

        a.href = data['link'];
        a.innerHTML = data['name'];

        li.appendChild(a);
        ul.appendChild(li);

        updateProgress();
    });

    source.addEventListener('badcreds', ev => {
        const data = JSON.parse((ev as MessageEvent).data);
        setError(`Bad credentials for ${data['account']} on ${data['site']}, you may need to log in again.`);
    });

    source.addEventListener('siteerror', ev => {
        const data = JSON.parse((ev as MessageEvent).data);
        setError(`Encountered an error when uploading to ${data['account']} on ${data['site']}: ${data['msg']}`);
    });

    source.addEventListener('httperror', ev => {
        const data = JSON.parse((ev as MessageEvent).data);
        setError(`Got status code ${data['code']} from ${data['site']} when uploading to ${data['account']}.`);
    });

    source.addEventListener('error', ev => {
        setError('A site error occured, please try again later.');

        Raven.captureException(ev);
    });

    source.addEventListener('done', () => {
        source.close();
        uploadClose.disabled = false;

        bar.classList.remove('progress-bar-animated');

        if (!hadError) {
            bar.classList.remove('bg-info');
            bar.classList.add('bg-success');
        }

        uploadClose.addEventListener('click', () => window.location.reload());
    });
}

function clickedSubmit(ev) {
    ev.preventDefault();

    const target = ev.target;
    if (target.classList.contains('disabled')) return;

    const id = target.parentNode.querySelector('input[name="id"]').value;
    target.classList.add('disabled');

    uploadWithEvents(id);
}

const submitButtons = Array.from(document.querySelectorAll('.submit-submission'));
submitButtons.forEach(button => button.addEventListener('click', clickedSubmit));

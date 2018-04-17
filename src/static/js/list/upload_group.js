class GroupUpload {
    constructor(id) {
        this.body = document.querySelector('#uploadModal .modal-body');
        this.close = document.querySelector('#uploadModal button');
        this.countDiv = document.createElement('div');
        this.bar = document.createElement('div');
        this.linkList = document.createElement('ul');
        this.delaying = document.createElement('div');
        this.hadError = false;
        this.count = 0;
        this.uploaded = 0;
        this.initHTML();
        this.source = new EventSource(`/upload/group/post?id=${id}`);
        this.source.addEventListener('count', this.gotCount.bind(this));
        this.source.addEventListener('groupdone', this.gotGroupDone.bind(this));
        this.source.addEventListener('upload', this.gotUpload.bind(this));
        this.source.addEventListener('delay', this.gotDelay.bind(this));
        this.source.addEventListener('done', this.gotDone.bind(this));
        this.source.addEventListener('error', this.gotError.bind(this));
        this.source.addEventListener('badcreds', this.gotBadCreds.bind(this));
        this.source.addEventListener('siteerror', this.gotSiteError.bind(this));
        this.source.addEventListener('httperror', this.gotHTTPError.bind(this));
    }
    updateProgress() {
        this.bar.style.width = `${Math.round(this.uploaded / this.count * 100)}%`;
    }
    gotCount(ev) {
        this.count = parseInt(ev.data, 10);
        this.bar.classList.add('progress-bar-animated');
        this.countDiv.innerHTML = `Uploading to ${this.count} sites.`;
    }
    gotUpload(ev) {
        const data = JSON.parse(ev.data);
        const li = document.createElement('li');
        const a = document.createElement('a');
        a.href = data['link'];
        a.innerHTML = data['name'];
        li.appendChild(a);
        this.linkList.appendChild(li);
    }
    gotGroupDone() {
        this.uploaded++;
        this.updateProgress();
    }
    gotDelay(ev) {
        if (ev.data === 'start') {
            this.bar.classList.remove('progress-bar-animated');
            this.delaying.classList.remove('d-none');
        }
        else {
            this.bar.classList.add('progress-bar-animated');
            this.delaying.classList.add('d-none');
        }
    }
    gotDone() {
        this.source.close();
        this.close.disabled = false;
        this.bar.classList.remove('progress-bar-animated');
        if (!this.hadError) {
            this.bar.classList.remove('bg-info');
            this.bar.classList.add('bg-success');
        }
        this.close.addEventListener('click', () => window.location.reload());
    }
    gotError(ev) {
        this.setError('A site error occured, please try again later.');
        Raven.captureException(ev);
        this.source.close();
    }
    gotBadCreds(ev) {
        const data = JSON.parse(ev.data);
        this.setError(`Credentials for ${data.account} on ${data.site} may have expired, please try readding the account`);
    }
    gotSiteError(ev) {
        const data = JSON.parse(ev.data);
        this.setError(`Encountered an error when uploading to ${data.account} on ${data.site}: ${data.msg}`);
    }
    gotHTTPError(ev) {
        const data = JSON.parse(ev.data);
        this.setError(`Got a HTTP error for ${data.account} on ${data.site}: ${data.code}`);
    }
    setError(message) {
        this.hadError = true;
        this.bar.classList.remove('bg-info');
        this.bar.classList.add('bg-warning');
        if (message) {
            const e = document.createElement('div');
            e.innerHTML = message;
            this.body.appendChild(e);
        }
    }
    initHTML() {
        this.body.innerHTML = '';
        this.body.appendChild(this.countDiv);
        const progress = document.createElement('div');
        progress.classList.add('progress');
        this.body.appendChild(progress);
        this.bar.classList.add('progress-bar', 'progress-bar-striped', 'bg-info');
        progress.appendChild(this.bar);
        const div = document.createElement('div');
        div.appendChild(this.linkList);
        uploadBody.appendChild(div);
        this.delaying.classList.add('d-none');
        this.delaying.innerHTML = 'Delaying to avoid site rate limits';
        this.body.appendChild(this.delaying);
    }
}
function uploadGroup(ev) {
    ev.preventDefault();
    const target = ev.target;
    if (target.classList.contains('disabled'))
        return;
    const id = target.parentNode.querySelector('input[name="group_id"]').value;
    target.classList.add('disabled');
    new GroupUpload(id);
}
Array.from(document.querySelectorAll('.group-upload')).forEach(button => button.addEventListener('click', uploadGroup));
//# sourceMappingURL=upload_group.js.map
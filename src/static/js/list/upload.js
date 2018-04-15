var uploadBody = document.querySelector('#uploadModal .modal-body');
var uploadClose = document.querySelector('#uploadModal button');
function uploadWithEvents(id) {
    var source = new EventSource("/upload/art/saved?id=" + id);
    var hadError = false;
    var count = 0;
    var uploaded = 0;
    uploadBody.innerHTML = '';
    var p = document.createElement('p');
    uploadBody.appendChild(p);
    var progress = document.createElement('div');
    progress.classList.add('progress');
    uploadBody.appendChild(progress);
    var bar = document.createElement('div');
    bar.classList.add('progress-bar', 'progress-bar-striped', 'bg-info');
    progress.appendChild(bar);
    var div = document.createElement('div');
    var ul = document.createElement('ul');
    div.appendChild(ul);
    uploadBody.appendChild(div);
    function updateProgress() {
        bar.style.width = Math.round(uploaded / count * 100) + "%";
    }
    function setError(message) {
        hadError = true;
        bar.classList.remove('bg-info');
        bar.classList.add('bg-warning');
        if (message) {
            var e = document.createElement('div');
            e.innerHTML = message;
            uploadBody.appendChild(e);
        }
    }
    source.addEventListener('count', function (ev) {
        count = parseFloat(ev.data);
        p.innerHTML = "Creating " + count + " submissions.";
        bar.classList.add('progress-bar-animated');
    });
    source.addEventListener('upload', function (ev) {
        uploaded++;
        var data = JSON.parse(ev.data);
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = data['link'];
        a.innerHTML = data['name'];
        li.appendChild(a);
        ul.appendChild(li);
        updateProgress();
    });
    source.addEventListener('badcreds', function (ev) {
        var data = JSON.parse(ev.data);
        setError("Bad credentials for " + data['account'] + " on " + data['site'] + ", you may need to log in again.");
    });
    source.addEventListener('siteerror', function (ev) {
        var data = JSON.parse(ev.data);
        setError("Encountered an error when uploading to " + data['account'] + " on " + data['site'] + ": " + data['msg']);
    });
    source.addEventListener('httperror', function (ev) {
        var data = JSON.parse(ev.data);
        setError("Got status code " + data['code'] + " from " + data['site'] + " when uploading to " + data['account'] + ".");
    });
    source.addEventListener('error', function (ev) {
        setError('A site error occured, please try again later.');
        Raven.captureException(ev);
    });
    source.addEventListener('done', function () {
        source.close();
        uploadClose.disabled = false;
        bar.classList.remove('progress-bar-animated');
        if (!hadError) {
            bar.classList.remove('bg-info');
            bar.classList.add('bg-success');
        }
        uploadClose.addEventListener('click', function () { return window.location.reload(); });
    });
}
function clickedSubmit(ev) {
    ev.preventDefault();
    var target = ev.target;
    if (target.classList.contains('disabled'))
        return;
    var id = target.parentNode.querySelector('input[name="id"]').value;
    target.classList.add('disabled');
    uploadWithEvents(id);
}
var submitButtons = Array.from(document.querySelectorAll('.submit-submission'));
submitButtons.forEach(function (button) { return button.addEventListener('click', clickedSubmit); });
//# sourceMappingURL=upload.js.map
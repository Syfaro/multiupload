const insertUserLink = () => {
    $('.add-user-modal').modal('hide');

    const values = [
        document.querySelector('.add-user-modal input[name="username"]').value,
        document.querySelector('.add-user-modal input[name="site_name"]:checked').value,
        document.querySelector('.add-user-modal input[name="link_type"]:checked').value
    ];

    const output = `<|${values.join(',')}|>`;
    const textArea = document.querySelector('textarea[name="description"]');
    const caretPos = textArea.selectionStart;
    textArea.value = textArea.value.substring(0, caretPos) + output + textArea.value.substring(caretPos);

    document.querySelector('.add-user-modal input[name="username"]').value = '';
};

const linkEventHandler = ev => {
    ev.preventDefault();
    insertUserLink();
};

document.querySelector('.add-user-link').addEventListener('click', linkEventHandler);
document.querySelector('.modal-body form').addEventListener('submit', linkEventHandler);

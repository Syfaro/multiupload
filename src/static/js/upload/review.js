const imagePreview = document.querySelector('.preview-image');

document.querySelector('.upload-image').addEventListener('change', (ev) => {
    let files = ev.target.files;
    if (!files) return;
    if (files.length > 1 || files.length === 0) return;
    imagePreview.src = URL.createObjectURL(files[0]);
});

const description = document.querySelector('[name=description]');
const keywords = document.querySelector('[name=keywords]');

const updateHeight = elem => {
    requestAnimationFrame(() => {
        elem.style.height = '';
        elem.style.height = Math.min(elem.scrollHeight + 10, 200) + 'px';
    });
};

[description, keywords].forEach(elem => {
    updateHeight(elem);

    elem.addEventListener('input', () => {
        updateHeight(elem);
    });
});

class ArtGroupUpload {
    constructor() {
        this.fileInputs = Array.from(document.querySelectorAll('input.upload-image'));
        this.titleInputs = Array.from(document.querySelectorAll('.custom-title'));
        this.mainTitle = document.querySelector('input[name="title"]');
        this.imagePreviews = Array.from(document.querySelectorAll('.preview-image')).sort(ArtGroupUpload.sortImages);
        this.addEventListeners();
        this.mainTitle.addEventListener('keyup', this.updateTitles.bind(this));
        this.titleInputs.forEach(input => input.addEventListener('focus', ArtGroupUpload.focusCustomTitle.bind(this)));
        this.titleInputs.forEach(input => input.addEventListener('blur', this.blurCustomTitle.bind(this)));
    }
    blurCustomTitle(ev) {
        requestAnimationFrame(() => {
            const target = ev.target;
            if (target.value == '' || target.value == this.mainTitle.value) {
                target.readOnly = true;
                target.value = this.mainTitle.value;
            }
        });
    }
    static focusCustomTitle(ev) {
        const target = ev.target;
        target.readOnly = false;
    }
    updateTitles() {
        requestAnimationFrame(() => {
            this.titleInputs
                .filter(input => input.readOnly)
                .forEach(input => input.value = this.mainTitle.value);
        });
    }
    static sortImages(a, b) {
        const first = parseInt(a.dataset.image, 10);
        const second = parseInt(b.dataset.image, 10);
        if (first < second)
            return -1;
        if (first > second)
            return 1;
        return 0;
    }
    fileWasUploaded(ev) {
        const files = ev.target.files;
        if (!files)
            return;
        if (files.length !== 1)
            return;
        const image = parseInt(ev.target.dataset.image, 10);
        this.imagePreviews[image - 1].src = URL.createObjectURL(files[0]);
    }
    addEventListeners() {
        this.fileInputs.forEach(input => input.addEventListener('change', this.fileWasUploaded.bind(this)));
    }
}
new ArtGroupUpload();
//# sourceMappingURL=group.js.map
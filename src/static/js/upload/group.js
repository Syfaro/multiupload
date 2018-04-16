class ArtGroupUpload {
    constructor() {
        this.fileInputs = Array.from(document.querySelectorAll('input.upload-image'));
        this.imagePreviews = Array.from(document.querySelectorAll('.preview-image')).sort(ArtGroupUpload.sortImages);
        this.addEventListeners();
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
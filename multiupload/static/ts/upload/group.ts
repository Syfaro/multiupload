class ArtGroupUpload {
    private fileInputs: HTMLInputElement[];
    private titleInputs: HTMLInputElement[];
    private mainTitle: HTMLInputElement;
    private imagePreviews: HTMLImageElement[];

    constructor() {
        this.fileInputs = Array.from(document.querySelectorAll('input.upload-image'));
        this.titleInputs = Array.from(document.querySelectorAll('.custom-title'));
        this.mainTitle = document.querySelector('input[name="title"]')! as HTMLInputElement;
        this.imagePreviews = Array.from(document.querySelectorAll('.preview-image')).sort(ArtGroupUpload.sortImages) as HTMLImageElement[];

        this.addEventListeners();

        this.mainTitle.addEventListener('keyup', this.updateTitles.bind(this));
        this.titleInputs.forEach(input =>
            input.addEventListener('focus', ArtGroupUpload.focusCustomTitle.bind(this)));
        this.titleInputs.forEach(input =>
            input.addEventListener('blur', this.blurCustomTitle.bind(this)));
    }

    private blurCustomTitle(ev) {
        requestAnimationFrame(() => {
            const target = ev.target as HTMLInputElement;
            if (target.value == '' || target.value == this.mainTitle.value) {
                target.readOnly = true;
                target.value = this.mainTitle.value;
            }
        });
    }

    private static focusCustomTitle(ev) {
        const target = ev.target as HTMLInputElement;

        target.readOnly = false;
    }

    private updateTitles() {
        requestAnimationFrame(() => {
            this.titleInputs
                .filter(input => input.readOnly)
                .forEach(input => input.value = this.mainTitle.value);
        });
    }

    private static sortImages(a: HTMLElement, b: HTMLElement) {
        const first = parseInt(a.dataset.image!, 10);
        const second = parseInt(b.dataset.image!, 10);

        if (first < second) return -1;
        if (first > second) return 1;
        return 0;
    }

    private fileWasUploaded(ev) {
        const files = ev.target.files;

        if (!files) return;
        if (files.length !== 1) return;

        const image = parseInt(ev.target.dataset.image!, 10);

        this.imagePreviews[image - 1].src = URL.createObjectURL(files[0]);
    }

    private addEventListeners() {
        this.fileInputs.forEach(input =>
            input.addEventListener('change', this.fileWasUploaded.bind(this)));
    }
}

new ArtGroupUpload();

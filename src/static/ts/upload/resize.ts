class TextBoxResizer {
    readonly elem: HTMLElement;
    maxHeight: number;

    constructor(elem: HTMLElement | null, maxHeight: number = 200) {
        if (!elem) return;

        this.maxHeight = maxHeight;

        this.elem = elem;
        this.elem.addEventListener('input', this.gotInput.bind(this));

        this.resize();
    }

    resize() {
        this.elem.style.height = '';
        this.elem.style.height = Math.min(this.elem.scrollHeight + 10, this.maxHeight) + 'px';
    }

    private gotInput() {
        requestAnimationFrame(this.resize.bind(this));
    }
}

new TextBoxResizer(document.querySelector('[name="description"]'));
new TextBoxResizer(document.querySelector('[name="keywords"]'));

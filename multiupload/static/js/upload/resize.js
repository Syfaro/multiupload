class TextBoxResizer {
    constructor(elem, maxHeight = 200) {
        if (!elem)
            return;
        this.maxHeight = maxHeight;
        this.elem = elem;
        this.elem.addEventListener('input', this.gotInput.bind(this));
        this.resize();
    }
    resize() {
        this.elem.style.height = '';
        this.elem.style.height = Math.min(this.elem.scrollHeight + 10, this.maxHeight) + 'px';
    }
    gotInput() {
        requestAnimationFrame(this.resize.bind(this));
    }
}
new TextBoxResizer(document.querySelector('[name="description"]'));
new TextBoxResizer(document.querySelector('[name="keywords"]'));
//# sourceMappingURL=resize.js.map
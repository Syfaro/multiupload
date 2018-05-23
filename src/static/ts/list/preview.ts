class ImagePreview {
    private submissions = Array.from(document.querySelectorAll('tbody tr:not([data-image="None"]) th')) as HTMLTableHeaderCellElement[];

    constructor() {
        this.submissions.forEach(submission => {
            $(submission).popover({
                content: function () {
                    const parent = this.parentNode;
                    const imageSrc = parent.dataset.image;

                    return `<img style="max-width: 200px; max-height: 200px;" src="/upload/imagepreview/${imageSrc}">`;
                },
                trigger: 'hover',
                html: true,
            })
        });
    }
}

new ImagePreview();

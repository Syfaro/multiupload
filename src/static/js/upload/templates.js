class TemplateLoader {
    constructor() {
        this.buttons = Array.from(document.querySelectorAll('.template-btn'));
        this.description = document.getElementById('description');
        this.templates = null;
        this.buttons.forEach(button => button.addEventListener('click', this.buttonClicked.bind(this)));
    }
    async buttonClicked(ev) {
        const button = ev.target;
        button.disabled = true;
        if (this.templates === null) {
            const templates = await this.loadTemplates();
            this.templates = templates;
        }
        let template = null;
        this.templates.forEach(t => {
            if (t['id'] == button.dataset.id) {
                template = t;
            }
        });
        if (template === null) {
            alert('Unknown template??');
            return;
        }
        this.description.value += '\n\n' + template['content'];
        this.description.dispatchEvent(new Event('input', {
            bubbles: true,
            cancelable: true
        }));
        button.disabled = false;
    }
    async loadTemplates() {
        const req = await fetch(Multiupload.endpoints.templates, {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
            },
        });
        const json = await req.json();
        return json['templates'];
    }
}
new TemplateLoader();
//# sourceMappingURL=templates.js.map
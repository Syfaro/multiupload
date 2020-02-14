class TemplateLoader {
    buttons: HTMLButtonElement[] = Array.from(document.querySelectorAll('.template-btn'));
    description: HTMLTextAreaElement = document.getElementById('description') as HTMLTextAreaElement;

    templates: object[] | null = null;

    constructor() {
        this.buttons.forEach(button => button.addEventListener('click', this.buttonClicked.bind(this)));
    }

    async buttonClicked(ev: Event) {
        const button = ev.target as HTMLButtonElement;

        button.disabled = true;

        if (this.templates === null) {
            const templates = await this.loadTemplates();
            this.templates = templates;
        }

        let template: object | null = null;

        this.templates!.forEach(t => {
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

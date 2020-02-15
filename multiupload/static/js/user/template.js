const h = preact.h;
const Component = preact.Component;
const render = preact.render;

function chunk(arr, len) {
    let chunks = [], i = 0;
    const n = arr.length;
    while (i < n)
        chunks.push(arr.slice(i, i += len));
    return chunks;
}
class SiteDescription extends Component {
    addLineBreaks() {
        return this.props.description.split('\n').map(line => {
            return [
                line,
                h("br", null)
            ];
        });
    }
    render() {
        return (h("div", { className: 'card mb-2' },
            h("div", { className: 'card-body' },
                h("h5", { className: 'card-title' }, this.props.title),
                h("p", { className: 'card-text' }, this.addLineBreaks()))));
    }
}
class DescriptionForm extends Component {
    updatedContent(ev) {
        if (typeof this.props.updatedContent === 'function') {
            this.props.updatedContent(ev);
        }
        const elem = ev.target;
        requestAnimationFrame(() => {
            elem.style.height = '';
            elem.style.height = Math.min(elem.scrollHeight + 10, 200) + 'px';
        });
    }
    render() {
        return (h("form", { method: 'POST', action: '/user/template', id: 'add' },
            h("input", { type: 'hidden', name: '_csrf_token', value: Multiupload.csrf }),
            h("div", { className: 'form-group' },
                h("label", { for: 'name' }, "Name"),
                h("input", { type: 'text', className: 'form-control', name: 'name', id: 'name', placeholder: 'Name' })),
            h("div", { className: 'form-group' },
                h("label", { for: 'content' }, "Content"),
                h("textarea", { className: 'form-control', name: 'content', id: 'content', placeholder: 'Content', onKeyUp: ev => this.updatedContent(ev) })),
            h("div", { className: 'form-group' },
                h("button", { type: 'submit', className: 'btn btn-primary form-control', disabled: !this.props.addEnabled }, "Add"))));
    }
}
class Descriptions extends Component {
    constructor(props) {
        super(props);
        this.state = {
            lastInput: '',
            currentInput: '',
            interval: undefined,
            descriptions: [],
            addEnabled: false
        };
    }
    componentDidMount() {
        let interval = setInterval(() => {
            if (this.state.lastInput == this.state.currentInput)
                return;
            this.setState({
                lastInput: this.state.currentInput
            });
            this.loadDescriptions(this.state.currentInput);
        }, 2000);
        this.setState({
            interval: interval
        });
    }
    componentWillUnmount() {
        clearInterval(this.state.interval);
    }
    async loadDescriptions(description) {
        let req = await fetch(Multiupload.endpoints.description, {
            body: JSON.stringify({
                'accounts': '1,2,3,4,5,7,8,100',
                'description': description,
            }),
            credentials: 'same-origin',
            method: 'POST',
            headers: {
                'X-CSRFToken': Multiupload.csrf,
                'Content-Type': 'application/json',
            },
        });
        let json = await req.json();
        this.setState({
            descriptions: json.descriptions,
            addEnabled: this.state.currentInput == this.state.lastInput
        });
    }
    gotKeyUp(ev) {
        this.setState({
            currentInput: ev.target.value,
            addEnabled: false
        });
    }
    render() {
        if (!this.state.descriptions) {
            return (h(DescriptionForm, { addEnabled: false, updatedContent: ev => this.gotKeyUp(ev) }));
        }
        ;
        let chunks = chunk(this.state['descriptions'], 2);
        let descriptions = chunks.map(chunk => h("div", { className: 'row' }, chunk.map(description => h("div", { className: 'col-md-6' },
            h(SiteDescription, { title: description.site, description: description.description })))));
        return (h("div", null,
            h(DescriptionForm, { addEnabled: this.state['addEnabled'], updatedContent: ev => this.gotKeyUp(ev) }),
            descriptions));
    }
}
render(h(Descriptions, null), document.getElementById('add-template'));
//# sourceMappingURL=template.js.map

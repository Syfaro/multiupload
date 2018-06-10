import { h, Component, render } from 'preact';

function chunk (arr: Array<any>, len: number) {
    let chunks: Array<any>[] = [], i = 0;
    const n = arr.length;

    while (i < n)
        chunks.push(arr.slice(i, i += len));

    return chunks;
}

interface SiteDescriptionProps {
    title: string;
    description: string;
}

class SiteDescription extends Component<SiteDescriptionProps, any> {
    addLineBreaks() {
        return this.props.description.split('\n').map(line => {
            return [
                line,
                <br />
            ]
        });
    }

    render() {
        return (
            <div className='card mb-2'>
                <div className='card-body'>
                    <h5 className='card-title'>{this.props.title}</h5>
                    <p className='card-text'>{this.addLineBreaks()}</p>
                </div>
            </div>
        );
    }
}

interface FormProps {
    updatedContent: (ev: Event) => void,
    addEnabled: boolean
}

class DescriptionForm extends Component<FormProps, any> {
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
        return (
            <form method='POST' action='/user/template' id='add'>
                <input type='hidden' name='_csrf_token' value={Multiupload.csrf} />

                <div className='form-group'>
                    <label for='name'>Name</label>
                    <input type='text' className='form-control' name='name' id='name' placeholder='Name' />
                </div>

                <div className='form-group'>
                    <label for='content'>Content</label>
                    <textarea className='form-control' name='content' id='content' placeholder='Content' onKeyUp={ ev => this.updatedContent(ev) } />
                </div>

                <div className='form-group'>
                    <button type='submit' className='btn btn-primary form-control' disabled={!this.props.addEnabled}>Add</button>
                </div>
            </form>
        );
    }
}

interface DescriptionProps {

}

interface DescriptionState {
    lastInput: string;
    currentInput: string;

    interval: number | undefined;

    descriptions: Array<any>;
    addEnabled: boolean;
}

class Descriptions extends Component<DescriptionProps, DescriptionState> {
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
            if (this.state.lastInput == this.state.currentInput) return;

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
            return (
                <DescriptionForm addEnabled={false} updatedContent={ ev => this.gotKeyUp(ev) } />
            );
        };

        let chunks = chunk(this.state['descriptions'], 2);

        let descriptions = chunks.map(chunk =>
            <div className='row'>
                {chunk.map(description =>
                    <div className='col-md-6'>
                        <SiteDescription title={description.site} description={description.description} />
                    </div>
                )}
            </div>
        );

        return (
            <div>
                <DescriptionForm addEnabled={this.state['addEnabled']} updatedContent={ ev => this.gotKeyUp(ev) } />
                {descriptions}
            </div>
        );
    }
}

render(<Descriptions />, document.getElementById('add-template')!);

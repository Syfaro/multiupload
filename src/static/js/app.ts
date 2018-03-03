import * as m from 'mithril';
import * as stream from 'mithril/stream';
import twitter from 'twitter-text';

const API_ENDPOINT = '/api/v1';

let selectedAccounts = stream([]);
let currentSubmission = stream({});

interface Account {
    id: number;
    site_id: number;
    site_name: string;
    username: string;
    used_last: boolean;
    selected: boolean;
}

interface Submission {
    title: string;
    tags: string;
    description: string;
    rating: string;
}

class NextButton {
    enabled: boolean;
    next: string;

    constructor(next, enabled = false) {
        this.next = next;
        this.enabled = enabled;
    }

    button() {
        return m('button', {
            disabled: !this.enabled,
            class: 'btn btn-primary btn-lg',
            onclick: () => {
                if (!this.enabled) return;
                m.route.set(this.next);
            }
        }, 'Next');
    }
}

class AccountSelection {
    accounts: Account[] = [];
    nextButton = new NextButton('/post');

    constructor() {
        this.loadAccounts();
    }

    loadAccounts() {
        m.request({
            method: 'GET',
            url: API_ENDPOINT + '/accounts',
            withCredentials: true,
        }).then(data => {
            this.accounts = data['accounts'];
        });
    }

    updateSelectedAccounts() {
        let hasSelected = false;

        selectedAccounts(this.accounts.filter(account => {
            if (account.selected) hasSelected = true;
            return account.selected;
        }));

        this.nextButton.enabled = hasSelected;
    }

    accountList() {
        return this.accounts.map((account, idx) => {
            return m('div', {class: 'form-check'},
                [
                    m('input', {
                        class: 'form-check-input',
                        type: 'checkbox',
                        name: 'account',
                        value: account.id,
                        id: `account-${account.id}`,
                        onclick: () => {
                            this.accounts[idx].selected = !this.accounts[idx].selected;
                            this.updateSelectedAccounts();
                        },
                    }),
                    m('label', {
                        class: 'form-check-label',
                        for: `account-${account.id}`,
                    }, `${account.site_name} - ${account.username}`),
                ]);
        });
    }

    view() {
        return m('div', {class: 'container'}, [
            m('h2', 'Account selection'),
            m('h3', 'Which accounts do you want to upload to?'),
            m('div', {class: 'row'},
                m('div', {class: 'col-sm-12'}, this.accountList())),
            m('div', {class: 'row'},
                m('div', {class: 'col-sm-12', style: {marginTop: '15px'}}, this.nextButton.button())),
        ]);
    }
}

interface DescriptionPreview {
    site: string;
    description: string;
}

class SubmissionInformation {
    nextButton = new NextButton('/upload');
    currentDescription: string;
    lastDescription: string;
    descriptionPreviews: DescriptionPreview[] = [];
    sites: any = [];

    username: string;
    linkType: number = 0;
    site: number;

    updateInterval: number;

    charsRemaining = 0;

    sub: Submission = {
        title: '',
        tags: '',
        description: '',
        rating: '',
    };

    constructor() {
        if (selectedAccounts().length === 0)
            m.route.set('/accounts');

        this.loadSites();
    }

    oncreate() {
        this.updateInterval = setInterval(() => {
            this.updateDescriptionPreview();
        }, 2000);
    }

    onremove() {
        console.log('removing');

        clearInterval(this.updateInterval);
    }

    view() {
        return m('div', {class: 'container'},
            [
                m('div', {class: 'row'},
                    m('div', {class: 'col-sm-12'}, m('h2', 'Submit info'))),
                m('div', {class: 'row'}, [
                    m('div', {class: 'col-sm-12 col-md-3'}, this.accountList()),
                    m('div', {class: 'col-sm-12 col-md-9'}, this.buildDataForm()),
                ]), m('div', {class: 'row'},
                    m('div', {class: 'col-sm-12'}, this.nextButton.button())),
                this.addLinkModal(),
            ]);
    }

    loadSites() {
        m.request({
            method: 'GET',
            url: API_ENDPOINT + '/sites',
        }).then(sites => {
            this.sites = sites['sites'];
        });
    }

    static inkbunnyMessage() {
        if (selectedAccounts().filter(account => account.site_id === 4).length === 0)
            return null;

        return m('div', {
            class: 'hidden'
        }, m('p', [
            'Please note that Inkbunny ',
            m('a', {
                href: 'https://wiki.inkbunny.net/wiki/Keyword_Policy#Minimum_Required_Keywords',
            }, 'requires'),
            ' keywords for sex, species, and essential themes.',
        ]))
    }

    formatTwitterPost(message: String): String {
        const sitesToReplace = this.sites.map(site => site['name'].toUpperCase() + '_URL');

        let newMessage = message;

        sitesToReplace.forEach(site => {
            newMessage = newMessage.replace(site, 'https://example.com');
        });

        console.log(newMessage);

        return newMessage;
    }

    hasAllItems() {
        this.nextButton.enabled = !(this.sub.title === '' || this.sub.tags === '' || this.sub.description === '' || this.sub.rating === '');
        currentSubmission(this.sub);
    }

    basicForm() {
        return [
            m('h3', 'Basic info'),
            [
                m('div', {
                    class: 'form-group',
                }, [
                    m('label', {
                        for: 'title'
                    }, 'Title'),
                    m('input', {
                        id: 'title',
                        type: 'text',
                        name: 'title',
                        class: 'form-control',
                        placeholder: 'Title',
                        oninput: m.withAttr('value', ev => {
                            this.sub.title = ev;
                            this.hasAllItems();
                        }),
                    })
                ]),
                m('div', {
                    class: 'form-group',
                }, [
                    m('label', {
                        for: 'keywords',
                    }, 'Tags / keywords'),
                    m('textarea', {
                        class: 'form-control',
                        name: 'keywords',
                        placeholder: 'Tags / keywords',
                        id: 'keywords',
                        oninput: m.withAttr('value', ev => {
                            this.sub.tags = ev;
                            this.hasAllItems();
                        }),
                    }),
                    m('p', {
                        class: 'help-block',
                    }, [
                        'Separate keywords with spaces. ',
                        m('abbr', {
                            title: 'A hashtag is any keyword that starts with an \'#\''
                        }, 'Hashtags will only be included on Twitter.')
                    ]),
                    SubmissionInformation.inkbunnyMessage(),
                ]),
                m('div', [
                    m('div', {class: 'form-check'}, [
                        m('input', {
                            class: 'form-check-input',
                            type: 'radio',
                            name: 'rating',
                            value: 'general',
                            id: 'general',
                            onchange: m.withAttr('checked', ev => {
                                if (ev) {
                                    this.sub.rating = 'general';
                                    this.hasAllItems();
                                }
                            })
                        }),
                        m('label', {
                            class: 'form-check-label',
                            for: 'general',
                        }, 'General'),
                    ]),
                    m('div', {class: 'form-check'}, [
                        m('input', {
                            class: 'form-check-input',
                            type: 'radio',
                            name: 'rating',
                            value: 'mature',
                            id: 'mature',
                            onchange: m.withAttr('checked', ev => {
                                if (ev) {
                                    this.sub.rating = 'mature';
                                    this.hasAllItems();
                                }
                            })
                        }),
                        m('label', {
                            class: 'form-check-label',
                            for: 'mature',
                        }, 'Mature'),
                    ]),
                    m('div', {class: 'form-check'}, [
                        m('input', {
                            class: 'form-check-input',
                            type: 'radio',
                            name: 'rating',
                            value: 'explicit',
                            id: 'explicit',
                            onchange: m.withAttr('checked', ev => {
                                if (ev) {
                                    this.sub.rating = 'explicit';
                                    this.hasAllItems();
                                }
                            })
                        }),
                        m('label', {
                            class: 'form-check-label',
                            for: 'explicit',
                        }, 'Explicit'),
                    ]),
                ]),
                m('div', {"class": "form-group"}, [
                    m('label', {"for": "twitter-text"}, 'Twitter Text'),
                    m('textarea', {
                        class: 'form-control',
                        id: 'twitter-text',
                        placeholder: 'Twitter text',
                        name: 'twitter-text',
                        oninput: m.withAttr('value', val => {
                            this.charsRemaining = twitter.getTweetLength(this.formatTwitterPost(val));
                        }),
                    }),
                    m('p', {
                        class: 'help-block',
                    }, `Enter the text to go on Twitter here. Entering SITENAME_URL will be replaced with the link for that site. You have ${280-this.charsRemaining} characters remaining.`)
                ])
            ]
        ]
    }

    addLinkModal() {
        return m('.modal', {
            class: 'add-user-modal fade',
        }, m('.modal-dialog',
            m('.modal-content', [
                m('.modal-header', [
                    m('h5', {
                        class: 'modal-title',
                    }, 'Link a user'),
                    m('button', {
                        class: 'close',
                        'data-dismiss': 'modal',
                    }, m('span', '×')),
                ]),
                m('.modal-body', [
                    m('.form-group',
                        m('input', {
                            type: 'text',
                            name: 'username',
                            class: 'form-control',
                            placeholder: 'Username',
                            value: this.username,
                            oninput: m.withAttr('value', val => {
                                this.username = val;
                            }),
                        })),
                    m('div', [
                        m('label', 'Please select which site this user is on.'),
                        this.sites.map(site => {
                            return m('.radio',
                                m('label', [
                                    m('input', {
                                        type: 'radio',
                                        name: 'site',
                                        value: site['id'],
                                        onchange: m.withAttr('checked', checked => {
                                            if (!checked) return;
                                            this.site = site['id'];
                                        })
                                    }),
                                    ` ${site.name}`,
                                ]));
                        })
                    ]),
                    m('div', [
                        m('label', 'Please select what kind of link you want it to be.'),
                        m('.radio', [
                            m('label', [
                                m('input', {
                                    type: 'radio',
                                    name: 'link',
                                    value: '0',
                                    checked: 'checked',
                                    onchange: m.withAttr('checked', checked => {
                                        if (!checked) return;
                                        this.linkType = 0;
                                    }),
                                }),
                                ' Just link',
                            ]),
                        ]),
                        m('.radio', [
                            m('label', [
                                m('input', {
                                    type: 'radio',
                                    name: 'link',
                                    value: '1',
                                    onchange: m.withAttr('checked', checked => {
                                        if (!checked) return;
                                        this.linkType = 1;
                                    }),
                                }),
                                ' Just profile picture',
                            ]),
                            m('p', {
                                class: 'help-block',
                            }, 'Note that this option may not be available on all sites. It may appear as a link.'),
                        ]),
                        m('.radio', [
                            m('label', [
                                m('input', {
                                    type: 'radio',
                                    name: 'link',
                                    value: '2',
                                    onchange: m.withAttr('checked', checked => {
                                        if (!checked) return;
                                        this.linkType = 2;
                                    }),
                                }),
                                ' Link and profile picture',
                            ]),
                            m('p', {
                                class: 'help-block',
                            }, 'Note that this option may not be available on all sites. It may appear as a link.'),
                        ])
                    ])
                ]),
                m('.modal-footer', [
                    m('button', {
                        type: 'button',
                        class: 'btn btn-default',
                        'data-dismiss': 'modal',
                    }, 'Cancel'),
                    m('button', {
                        type: 'button',
                        class: 'btn btn-primary',
                        'data-dismiss': 'modal',
                        onclick: ev => {
                            ev.preventDefault();

                            this.addSiteLink();
                            this.username = '';
                        }
                    }, 'Add user link'),
                ])
            ])));
    }

    addSiteLink() {
        const output = `<|${this.username},${this.site},${this.linkType}|>`;
        const textArea = <HTMLInputElement>document.querySelector('textarea[name="description"]');

        const caretPos = textArea.selectionStart;
        textArea.value = textArea.value.substring(0, caretPos) + output + textArea.value.substring(caretPos);
    }

    updateDescriptionPreview() {
        if (this.lastDescription === this.currentDescription) return;

        this.lastDescription = this.currentDescription;
        this.sub.description = this.currentDescription;

        const selected = selectedAccounts();

        m.request({
            method: 'POST',
            url: API_ENDPOINT + '/description',
            withCredentials: true,
            data: {
                'accounts': selected.map(account => account.site_id).join(','),
                'description': this.lastDescription,
            }
        }).then(data => {
            this.descriptionPreviews = data['descriptions'];
        });
    }

    displayDescriptionPreviews() {
        if (this.descriptionPreviews.length === 0) return null;

        return [
            m('h3', {style: {marginTop: '8px'}}, 'Description previews'),
            m('div', this.descriptionPreviews.map(preview => {
                return m('.card', {style: {marginBottom: '8px'}},
                    m('.card-body',
                        m('h5', {
                            class: 'card-title',
                        }, preview.site),
                    m('p', {
                        class: 'card-text',
                    }, m.trust(preview.description))));
            }))
        ];
    }

    descriptionForm() {
        return [
            m('h3', 'Description'),
            m('div', {class: 'form-group'}, [
                m('label', {
                    for: 'description',
                }, 'Description'),
                m('textarea', {
                    id: 'descrption',
                    class: 'form-control',
                    name: 'description',
                    placeholder: 'Description',
                    oninput: m.withAttr('value', ev => {
                        this.currentDescription = ev;
                        this.sub.description = ev;
                        this.hasAllItems();
                    }),
                })
            ]),
            m('button', {
                type: 'button',
                class: 'btn btn-default btn-sm',
                'data-toggle': 'modal',
                'data-target': '.add-user-modal',
            }, 'Add user link'),
            this.displayDescriptionPreviews(),
        ]
    }

    buildDataForm() {
        return m('div', {class: 'row'}, [
            m('div', {class: 'col-sm-12 col-md-4'}, this.basicForm()),
            m('div', {class: 'col-sm-12 col-md-8'}, this.descriptionForm()),
        ]);
    }

    accountList() {
        return [
            m('h3', 'Selected accounts'),
            m('ul',
            selectedAccounts().map(account => {
                return m('li', `${account.site_name} - ${account.username}`);
            }))
        ];
    }
}

class SubmitPost {
    imageSource: string = null;
    image: File = null;

    constructor() {
        if (!currentSubmission()['description'])
            m.route.set('/post');
    }

    imagePreview() {
        if (this.imageSource === null) return null;

        return m('.row',
            m('.col-sm-12',
                m('img', {
                    class: 'img-fluid mx-auto',
                    src: this.imageSource,
                })));
    }

    uploadForm() {
        return m('.row',
            m('.col-sm-12',
                m('.form-group', [
                m('label', {
                    for: 'file',
                }),
                m('input', {
                    type: 'file',
                    class: 'form-control-file',
                    id: 'file',
                    onchange: m.withAttr('files', files => {
                        this.image = null;
                        this.imageSource = null;

                        if (files.length !== 1) return;

                        this.image = files[0];
                        this.imageSource = URL.createObjectURL(files[0]);
                    }),
                }),
            ])));
    }

    submitButton() {
        return m('.row',
            m('.col-sm-12',
                m('button', {
                    class: 'btn btn-primary btn-lg',
                    disabled: this.image === null,
                    onclick: ev => {
                        ev.preventDefault();

                        console.log(selectedAccounts(), currentSubmission(), this.image);
                    },
                }, 'Submit')));
    }

    view() {
        return m('.container', [
            m('.row',
                m('.col-sm-12', [
                m('h2', 'Submission upload'),
            ])),
            this.imagePreview(),
            this.uploadForm(),
            this.submitButton(),
        ]);
    }
}

m.route.prefix('/beta');

m.route(document.body, '/accounts', {
    '/accounts': AccountSelection,
    '/post': SubmissionInformation,
    '/upload': SubmitPost,
});

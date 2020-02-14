class LoadingSpinner {
    constructor(spinner = '.spinner', className = 'd-none') {
        this.className = 'd-none';
        this.isVisible = false;
        const elem = document.querySelector(spinner);
        if (!elem)
            throw new Error('Unknown spinner element');
        this.className = className;
        this.spinner = elem;
        this.spinner.classList.add(this.className);
    }
    show() {
        this.spinner.classList.remove(this.className);
        this.isVisible = true;
    }
    hide() {
        this.spinner.classList.add(this.className);
        this.isVisible = false;
    }
    toggle() {
        if (this.isVisible)
            this.spinner.classList.add(this.className);
        else
            this.spinner.classList.remove(this.className);
        this.isVisible = !this.isVisible;
    }
}
class DeviantArtUpload {
    constructor() {
        this.accounts = Array.from(document.querySelectorAll('input[name="account"][data-site="8"]'));
        this.folderInput = document.querySelector('.da-folders');
        this.folders = document.querySelector('.deviantart-folders');
        this.categories = document.querySelector('.deviantart-categories');
        this.hasExisting = document.querySelector('input[name="deviantart-category"]').value;
        this.mature = document.querySelector('.deviantart-mature');
        this.ratings = Array.from(document.querySelectorAll('input[name="rating"]'));
        this.box = document.querySelector('.deviantart-category');
        this.categoryLoading = new LoadingSpinner('.spinner-categories');
        this.folderLoading = new LoadingSpinner('.spinner-folders');
        this.getFolders();
        this.ratings.forEach(rating => rating.addEventListener('change', this.updateRating.bind(this)));
        this.accounts.forEach(account => account.addEventListener('change', () => {
            this.updateBox();
            this.getFolders();
        }));
        setTimeout(this.updateBox.bind(this), 250);
        this.getFolders();
    }
    selectChanged(ev) {
        const selected = ev.target.querySelectorAll('option:checked');
        const account = ev.target.dataset.account;
        const selections = {};
        Array.from(selected).forEach(selection => {
            if (!selections[account])
                selections[account] = [];
            selections[account].push(selection.value);
        });
        this.folderInput.value = JSON.stringify(selections);
    }
    getFolders() {
        const value = this.folderInput.value;
        const selected = value.length > 0 ? JSON.parse(value) : {};
        this.folders.innerHTML = '';
        DeviantArtUpload.getSelectedAccounts().forEach(async (account) => {
            const accountSelected = selected[account.value] === undefined ? ['None'] : selected[account.value];
            const div = document.createElement('div');
            const name = document.createElement('label');
            name.classList.add('mt-2');
            name.innerHTML = `DeviantArt Folders — ${account.dataset.account}`;
            div.appendChild(name);
            this.folders.appendChild(div);
            this.folderLoading.show();
            const data = await fetch(`/api/v1/deviantart/folders?account=${account.value}`, {
                credentials: 'same-origin',
            });
            const folders = await data.json();
            this.folderLoading.hide();
            const select = document.createElement('select');
            select.addEventListener('change', this.selectChanged.bind(this));
            select.dataset.account = account.value;
            select.multiple = true;
            select.classList.add('form-control');
            folders['folders'].unshift({
                'name': 'None',
                'folderid': 'None',
            });
            folders['folders'].forEach(folder => {
                const option = document.createElement('option');
                option.innerHTML = folder['name'];
                option.value = folder['folderid'];
                if (accountSelected.includes(folder['folderid']))
                    option.selected = true;
                select.appendChild(option);
            });
            div.appendChild(select);
        });
    }
    async getCategories(selected) {
        const accountID = this.accounts[0].value;
        const selects = Array.from(document.querySelectorAll('.deviantart-categories select'));
        if (selected.length > 1 && selected[0] === '/')
            selected = selected.substr(1);
        selects.forEach(select => select.disabled = true);
        this.categoryLoading.show();
        const data = await fetch(`/api/v1/deviantart/category?account=${accountID}&path=${selected}`, {
            credentials: 'same-origin'
        });
        const json = await data.json();
        this.categoryLoading.hide();
        selects.forEach(select => select.disabled = false);
        return json['categories'];
    }
    categorySelected(ev) {
        const target = ev.target;
        const val = target.options[target.selectedIndex];
        if (val.dataset.hasChild !== 'false') {
            this.addSubCategory(val.value);
        }
        else {
            const category = document.querySelector('input[name="deviantart-category"]');
            if (category)
                category.value = val.value;
        }
        while (target.nextSibling) {
            target.parentNode.removeChild(target.nextSibling);
        }
    }
    addCategories(categories, selected = null) {
        if (categories.length === 0)
            return;
        if (selected && selected[0] === '/')
            selected = selected.substr(1);
        const select = document.createElement('select');
        select.classList.add('form-control', 'mb-2');
        select.addEventListener('input', this.categorySelected.bind(this));
        categories.unshift({
            title: 'Select One',
            catpath: '',
            has_subcategory: false,
        });
        categories.forEach(category => {
            const option = document.createElement('option');
            option.innerHTML = category['title'];
            option.value = category['catpath'];
            option.dataset.hasChild = category['has_subcategory'];
            select.appendChild(option);
        });
        if (selected !== null)
            select.value = selected;
        this.categories.appendChild(select);
    }
    async addSubCategory(subcat) {
        const categories = await this.getCategories(subcat);
        this.addCategories(categories);
    }
    async loadExisting() {
        let parts = this.hasExisting.split('/');
        parts.unshift('/');
        let prev = '';
        let prevParts = [];
        for (const idx in parts) {
            const part = parts[idx];
            let path = `${prev}${prev.length > 1 ? '/' : ''}${part}`;
            if (part !== '/')
                prevParts.push(part);
            let categories = await this.getCategories(path);
            this.addCategories(categories, prevParts.join('/') + (prevParts.length > 0 ? '/' : '') + parts[idx + 1]);
            prev = path;
        }
    }
    updateRating(ev) {
        const target = ev.target;
        if (!target.checked)
            return;
        if (target.value !== 'general') {
            this.mature.classList.remove('d-none');
            return;
        }
        const contentFields = Array.from(document.querySelectorAll('input[name="da-content"]'));
        Array.from(contentFields).forEach(input => input.checked = false);
        this.mature.classList.add('d-none');
    }
    updateBox() {
        const hasChecked = document.querySelectorAll('input[name="account"][data-site="8"]:checked');
        if (hasChecked.length > 0) {
            this.box.classList.remove('d-none');
            this.categories.innerHTML = '';
            if (this.hasExisting.length === 0)
                this.addSubCategory('/');
            else
                this.loadExisting();
        }
        else {
            this.box.classList.add('d-none');
        }
    }
    static getSelectedAccounts() {
        return Array.from(document.querySelectorAll('input[name="account"][data-site="8"]:checked'));
    }
}
new DeviantArtUpload();
//# sourceMappingURL=deviantart.js.map
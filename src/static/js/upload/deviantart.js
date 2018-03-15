const deviantArtAccounts = document.querySelectorAll('input[name="account"][data-site="8"]');
const deviantArtBox = document.querySelector('.deviantart-category');
const deviantArtCategories = document.querySelector('.deviantart-categories');

const loadingSpinner = document.querySelector('.spinner');
const hasExisting = document.querySelector('input[name="deviantart-category"]').value;

const getCategories = selected => {
    const accountID = deviantArtAccounts[0].value;
    const selects = document.querySelectorAll('.deviantart-categories select');

    if (selected.length > 1 && selected[0] === '/') selected = selected.substr(1);

    loadingSpinner.classList.remove('d-none');
    selects.forEach(select => select.disabled = 'disabled');

    return new Promise(resolve => {
        fetch(`/api/v1/deviantart/category?account=${accountID}&path=${selected}`, {
            credentials: 'same-origin'
        }).then(resp => resp.json()).then(json => {
            resolve(json['categories']);

            loadingSpinner.classList.add('d-none');
            selects.forEach(select => select.removeAttribute('disabled'));
        });
    });
};

const addCategories = (categories, selected = null) => {
    if (categories.length === 0) return;
    if (selected && selected[0] === '/') selected = selected.substr(1);

    const select = document.createElement('select');
    select.classList.add('form-control', 'mb-2');

    select.addEventListener('input', ev => {
        const target = ev.target;
        const val = target.options[target.selectedIndex];

        if (val.dataset.hasChild !== 'false') {
            addSubCategory(val.value);
        } else {
            document.querySelector('input[name="deviantart-category"]').value = val.value;
        }

        while (select.nextSibling) {
            select.parentNode.removeChild(select.nextSibling);
        }
    });

    categories.unshift({
        'title': 'Select One',
        'catpath': '',
        'has_subcategory': 'false'
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

    deviantArtCategories.appendChild(select);
};

const addSubCategory = subcat => {
    getCategories(subcat).then(categories => {
        addCategories(categories);
    });
};

const updateDeviantArtBox = () => {
    const hasChecked = document.querySelectorAll('input[name="account"][data-site="8"]:checked');

    if (hasChecked.length > 0) {
        deviantArtBox.classList.remove('d-none');

        deviantArtCategories.innerHTML = '';

        if (hasExisting.length === 0) addSubCategory('/');
        else loadExisting();
    } else {
        deviantArtBox.classList.add('d-none');
    }
};

const loadExisting = async () => {
    let parts = hasExisting.split('/');
    parts.unshift('/');

    let prev = '';
    let prevParts = [];

    for (let [idx, part] of parts.entries()) {
        let path = `${prev}${prev.length > 1 ? '/' : ''}${part}`;

        if (part !== '/') prevParts.push(part);

        let categories = await getCategories(path);
        addCategories(categories, prevParts.join('/') + (prevParts.length > 0 ? '/' : '') + parts[idx + 1]);

        prev = path;
    }
};

for (let i = 0; i < deviantArtAccounts.length; i++) {
    deviantArtAccounts[i].addEventListener('change', () => {
        updateDeviantArtBox();
    });
}

setTimeout(updateDeviantArtBox, 250);

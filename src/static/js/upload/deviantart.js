const deviantArtAccounts = document.querySelectorAll('input[name="account"][data-site="8"]');
const deviantArtBox = document.querySelector('.deviantart-category');
const deviantArtCategories = document.querySelector('.deviantart-categories');

const loadingSpinner = document.querySelector('.spinner');

const getCategories = selected => {
    loadingSpinner.style.display = 'block';

    const accountID = deviantArtAccounts[0].value;

    return new Promise(resolve => {
        fetch(`/api/v1/deviantart/category?account=${accountID}&path=${selected}`, {
            credentials: 'same-origin'
        }).then(resp => resp.json()).then(json => {
            resolve(json['categories']);

            loadingSpinner.style.display = 'none';
        });
    });
};

const addSubCategory = subcat => {
    getCategories(subcat).then(categories => {
        const select = document.createElement('select');
        select.classList.add('form-control', 'mb-2');

        select.addEventListener('input', ev => {
            const target = ev.target;
            const val = target.options[target.selectedIndex];

            if (val.dataset.hasChild !== 'false') addSubCategory(val.value);
            else {
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

        deviantArtCategories.appendChild(select);
    });
};

const updateDeviantArtBox = () => {
    const hasChecked = document.querySelectorAll('input[name="account"][data-site="8"]:checked');

    if (hasChecked.length > 0) {
        deviantArtBox.classList.remove('d-none');

        deviantArtCategories.innerHTML = '';
        addSubCategory('/');
    } else {
        deviantArtBox.classList.add('d-none');
    }
};

for (let i = 0; i < inkbunny.length; i++) {
    deviantArtAccounts[i].addEventListener('change', () => {
        updateDeviantArtBox();
    });
}

updateDeviantArtBox();

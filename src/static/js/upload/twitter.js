const sites = document.querySelectorAll('input[name="account"]');
const formats = document.querySelectorAll('input[name="twitter-fmt"]');
const twitterAccount = document.querySelector('input[name="twitter-account"]');
const format = document.querySelector('input[name="twitter-format"]');

const hasSiteSelected = (id) => twitterAccount.value.split(' ').includes(id.toString());

const updateTwitterLinks = () => {
    let hasTwitterSelected = false;

    for (let i = 0; i < sites.length; i++) {
        if (sites[i].dataset.site === '100' && sites[i].checked) {
            hasTwitterSelected = true;
            break;
        }
    }

    if (!hasTwitterSelected) {
        document.querySelector('.twitter-link').classList.add('d-none');
        return;
    }

    let otherSitesSelected = [];

    if (format.value === 'single') {
        otherSitesSelected.push({
            site: null,
        });
    }

    for (let i = 0; i < sites.length; i++) {
        if (!sites[i].checked || sites[i].dataset.site === '100') {
            continue;
        }

        const data = sites[i].dataset;

        otherSitesSelected.push({
            site: data.site,
            siteName: data.siteName,
            userName: data.account,
            id: sites[i].value
        });
    }

    if (otherSitesSelected.length === 0) {
        document.querySelector('.twitter-link').classList.add('d-none');
        return;
    }

    document.querySelector('.twitter-links').innerHTML = '';

    const links = document.querySelector('.twitter-links');

    for (let i = 0; i < otherSitesSelected.length; i++) {
        const item = document.createElement('div');
        item.classList.add('form-check');

        const checkbox = document.createElement('input');
        checkbox.classList.add('form-check-input');
        checkbox.type = format.value === 'multi' ? 'checkbox' : 'radio';
        checkbox.value = otherSitesSelected[i].id;
        checkbox.name = 'twitterlink';
        checkbox.id = 'site' + otherSitesSelected[i].id;
        if (otherSitesSelected[i].site !== null && hasSiteSelected(otherSitesSelected[i].id)) checkbox.checked = true;

        const label = document.createElement('label');
        label.classList.add('form-check-label');
        if (otherSitesSelected[i].site === null) {
            label.innerHTML = 'None';
        } else {
            label.innerHTML = otherSitesSelected[i].siteName + ' - ' + otherSitesSelected[i].userName;
        }
        label.htmlFor = 'site' + otherSitesSelected[i].id;

        checkbox.addEventListener('change', ev => {
            if (!ev.target.checked) return;

            if (format.value === 'multi') {
                let accounts = twitterAccount.value.split(' ');
                accounts.push(ev.target.value);
                twitterAccount.value = accounts.join(' ');
            } else {
                twitterAccount.value = ev.target.value;
            }
        });

        item.appendChild(checkbox);
        item.appendChild(label);
        links.appendChild(item);
    }

    if (format.value === 'single') {
        let items = twitterAccount.value.split(' ');
        if (items.length > 1)
            twitterAccount.value = items[0];
    }

    document.querySelector('.twitter-link').classList.remove('d-none');
};

updateTwitterLinks();

for (let i = 0; i < sites.length; i++) {
    sites[i].addEventListener('change', updateTwitterLinks);
}

formats.forEach(item => {
    item.addEventListener('change', ev => {
        if (!ev.target.checked) return;
        format.value = ev.target.value;
        updateTwitterLinks();
    });
});

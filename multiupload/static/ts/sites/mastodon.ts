const siteInputs: HTMLInputElement[] = Array.from(document.querySelectorAll('input[name="account"]'));
const mastodonItems = document.querySelector('.mastodon-link')!;

function updateMastodonLinks(): void {
    let hasMastodonSelected = false;

    siteInputs.forEach(site => {
        if (site.dataset.site === '101' && site.checked) {
            hasMastodonSelected = true;
        }
    });

    if (!hasMastodonSelected) {
        mastodonItems.classList.add('d-none');
    } else {
        mastodonItems.classList.remove('d-none');
    }
}

updateMastodonLinks();

siteInputs.forEach(site => site.addEventListener('change', updateMastodonLinks));

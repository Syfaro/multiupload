class FolderDisplay {
    constructor() {
        this.accounts = Array.from(document.querySelectorAll('input[name="account"]'));
        this.folders = Array.from(document.querySelectorAll('.folders'));
        this.accounts.forEach(account => account.addEventListener('change', this.updateFolders.bind(this)));
        this.updateFolders();
    }
    updateFolders() {
        const selectedSites = [];
        this.accounts.forEach(account => {
            if (account.checked) {
                selectedSites.push(parseInt(account.dataset.site, 10));
            }
        });
        this.folders.forEach(folder => {
            const site = parseInt(folder.dataset.site, 10);
            if (selectedSites.includes(site)) {
                folder.classList.remove('d-none');
            }
            else {
                folder.classList.add('d-none');
            }
        });
    }
}
new FolderDisplay();
//# sourceMappingURL=folders.js.map
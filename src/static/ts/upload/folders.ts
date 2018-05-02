class FolderDisplay {
    private accounts = Array.from(document.querySelectorAll('input[name="account"]')) as HTMLInputElement[];
    private folders = Array.from(document.querySelectorAll('.folders')) as HTMLSelectElement[];

    constructor() {
        this.accounts.forEach(account =>
            account.addEventListener('change', this.updateFolders.bind(this)));

        this.updateFolders();
    }

    private updateFolders() {
        const selectedAccounts: number[] = [];

        this.accounts.forEach(account => {
            if (account.checked) {
                selectedAccounts.push(parseInt(account.dataset.accountId!, 10));
            }
        });

        this.folders.forEach(folder => {
            const site = parseInt(folder.dataset.account!, 10);

            if (selectedAccounts.includes(site)) {
                folder.classList.remove('d-none');
            } else {
                folder.classList.add('d-none');
            }
        });
    }
}

new FolderDisplay();

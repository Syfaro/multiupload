const inkbunny = document.querySelectorAll('input[name="account"][data-site="4"]');
const inkbunnyMessage = document.querySelector('.inkbunny-message');

const updateInkbunnyMessage = () => {
    const hasChecked = document.querySelectorAll('input[name="account"][data-site="4"]:checked');

    if (hasChecked.length > 0) {
        inkbunnyMessage.classList.remove('d-none');
    } else {
        inkbunnyMessage.classList.add('d-none');
    }
};

Array.from(inkbunny).forEach(account => account.addEventListener('change', updateInkbunnyMessage));
updateInkbunnyMessage();

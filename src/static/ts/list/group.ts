declare const Multiupload;

const inputCheckboxes = Array.from(document.querySelectorAll('input[type="checkbox"]')) as [HTMLInputElement];
const selectActions = Array.from(document.querySelectorAll('.select-action')) as [HTMLAnchorElement];
const newGroupName = document.querySelector('.new-group-name') as HTMLDivElement;
const groupSelect = document.querySelector('.group-select') as HTMLSelectElement;
const groupName = document.querySelector('input[name="group-name"]') as HTMLInputElement;
const groupButton = document.querySelector('.add-to-group') as HTMLButtonElement;

function inputChange() {
    requestAnimationFrame(() => {
        const checked = inputCheckboxes.filter(box => box.checked);

        selectActions.forEach(action => {
            if (checked.length > 0) {
                action.classList.remove('disabled');
            } else {
                action.classList.add('disabled');
            }
        });
    });
}

function groupSelectChange(ev) {
    const target = ev.target as HTMLSelectElement;

    if (target.value === 'new') {
        newGroupName.classList.remove('d-none');
    } else {
        newGroupName.classList.add('d-none');
    }
}

async function addToGroup(ev) {
    ev.preventDefault();

    groupButton.disabled = true;
    groupButton.classList.add('progress-bar-striped', 'progress-bar-animated');

    const posts = inputCheckboxes
        .filter(input => input.checked)
        .map(input => parseInt(input.dataset.id!, 10));

    await fetch(Multiupload.endpoints.group.add, {
        method: 'POST',
        credentials: 'same-origin',
        redirect: 'manual',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': Multiupload.csrf,
        },
        body: JSON.stringify({
            'posts': posts,
            'group_id': (groupSelect.value === 'new' ? null : parseInt(groupSelect.value, 10)),
            'group_name': groupName.value,
        }),
    });

    groupButton.classList.remove('progress-bar-animated');
    groupButton.classList.add('bg-success');

    window.location.reload();
}

selectActions.forEach(action => action.addEventListener('click', ev => ev.preventDefault()));
inputCheckboxes.forEach(checkbox => checkbox.addEventListener('change', inputChange));
groupSelect.addEventListener('change', groupSelectChange);
groupButton.addEventListener('click', addToGroup);

const inputs = Array.from(document.querySelectorAll('input[type="checkbox"]'));
const actions = Array.from(document.querySelectorAll('.select-action'));
const newGroupName = document.querySelector('.new-group-name');
const groupSelect = document.querySelector('.group-select');
const groupName = document.querySelector('input[name="group-name"]');

inputs.forEach(input => input.addEventListener('change', () => {
    requestAnimationFrame(() => {
        const checked = inputs.filter(i => i.checked === true);

        actions.forEach(action => {
            if (checked.length > 0) {
                action.classList.remove('disabled');
            } else {
                action.classList.add('disabled');
            }
        })
    });
}));

actions.forEach(action => {
    action.addEventListener('click', ev => {
        ev.preventDefault();
    })
});

groupSelect.addEventListener('change', ev => {
    if (ev.target.value === 'new') {
        newGroupName.classList.remove('d-none');
    } else {
        newGroupName.classList.add('d-none');
    }
});

document.querySelector('.add-to-group').addEventListener('click', ev => {
    ev.preventDefault();

    fetch('/list/group/add', {
        method: 'POST',
        credentials:'same-origin',
        redirect: 'manual',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            'posts': inputs.filter(input => input.checked).map(input => parseInt(input.dataset.id, 10)),
            'group_id': (groupSelect.value === 'new' ? null : parseInt(groupSelect.value, 10)),
            'group_name': groupName.value,
        }),
    }).then(() => {
        window.location.reload();
    });

    $('#addGroupModal').modal('hide');
});

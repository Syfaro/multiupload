$('.description-preview-modal').on('show.bs.modal', function () {
    const body = document.querySelector('.description-preview-modal .modal-body');
    body.innerHTML = 'Loading&hellip;';

    $.ajax({
        type: 'GET',
        url: '/preview/description',
        data: $('input[name="account"], #description').serialize()
    }).always(function (data) {
        body.innerHTML = '';

        for (let i = 0; i < data.descriptions.length; i++) {
            const description = data.descriptions[i];

            const card = document.createElement('div');
            card.classList.add('card', 'mb-2');

            const cardBody = document.createElement('div');
            cardBody.classList.add('card-body');

            const cardTitle = document.createElement('h5');
            cardTitle.classList.add('card-title');
            cardTitle.innerHTML = description.site;

            const cardDesc = document.createElement('p');
            cardDesc.classList.add('card-text');
            $(cardDesc).text(description.description);

            cardBody.appendChild(cardTitle);
            cardBody.appendChild(cardDesc);
            card.appendChild(cardBody);
            body.appendChild(card);
        }
    });
});
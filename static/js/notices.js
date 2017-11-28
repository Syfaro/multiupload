(function () {
	'use strict';

	const items = document.querySelectorAll('button.close');

	if (!items) {
		return;
	}

	items.forEach(item => {
		item.addEventListener('click', ev => {
			const alert = ev.target.parentNode.parentNode;
			const id = alert.querySelector('span[data-id]').dataset.id;

			fetch(`/dismiss/${id}`, {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
			}).then(res => {
				alert.classList.add('hidden');
			});
		});
	});
}());

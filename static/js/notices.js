(function () {
	'use strict';

	var items = document.querySelectorAll('button.close');

	if (!items) {
		return;
	}

	Array.from(items).forEach(function (item) {
		item.addEventListener('click', function (ev) {
			var alert = ev.target.parentNode.parentNode;
			var id = alert.querySelector('span[data-id]').dataset.id;

			fetch('/dismiss/' + id, {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
			}).then(function (res) {
				alert.classList.add('hidden');
			});
		});
	});
}());

(function () {
	'use strict';

	var items = document.querySelectorAll('button.close');

	if (!items) {
		return;
	}

	Array.from(items).forEach(function (item) {
		item.addEventListener('click', function (ev) {
			var alert = ev.target.parentNode.parentNode;
			var span = alert.querySelector('span[data-id]');

			if (!span) {
				return;
			}

			var id = span.dataset.id;

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

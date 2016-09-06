(function () {
	'use strict';

	var items = document.querySelectorAll('button.close');

	if (!items) {
		return;
	}

	for (var i = 0; i < items.length; i++) {
		var item = items[i];

		item.addEventListener('click', function(e) {
			var alert = e.target.parentNode.parentNode;
			var id = e.target.dataset.id;

			var xhr = new XMLHttpRequest();
			xhr.open('POST', '/dismiss/' + id);
			xhr.onload = function () {
				alert.classList.add('hidden');
			};
			xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
			xhr.send('_csrf_token=' + csrf);
		});
	}
}())

const imagePreview = document.querySelector('.preview-image');

document.querySelector('.upload-image').addEventListener('change', ev => {
	imagePreview.src = URL.createObjectURL(this.files[0]);
});

[document.querySelector('.description'), document.querySelector('.keywords')].forEach(item => {
	item.addEventListener('input', () => {
		this.style.height = '';
		this.style.height = Math.min(this.scrollHeight+10, 200) + 'px';
	});
});

document.querySelector('.add-user-link').addEventListener('click', ev => {
	insertUserLink();
});

document.querySelector('.modal-body form').addEventListener('submit', ev => {
	ev.preventDefault();

	insertUserLink();
});

const inkbunny = document.querySelectorAll('input[name="account"][data-site="4"]');
const inkbunnyMessage = document.querySelector('.inkbunny-message');

const updateInkbunnyMessage = function () {
	const hasChecked = document.querySelectorAll('input[name="account"][data-site="4"]:checked');

	if (hasChecked.length > 0) {
		inkbunnyMessage.classList.remove('hidden');
	} else {
		inkbunnyMessage.classList.add('hidden');
	}
};

inkbunny.forEach(item => {
	item.addEventListener('change', ev => updateInkbunnyMessage());
});

updateInkbunnyMessage();

const sites = document.querySelectorAll('input[name="account"]');
const updateTwitterLinks = function () {
	let hasTwitterSelected = false;

	sites.forEach(site => {
		if (site.dataset.site == '100' && site.checked) {
			hasTwitterSelected = true;
		}
	});

	if (!hasTwitterSelected) {
		document.querySelector('.twitter-link').classList.add('hidden');
		return;
	}

	let otherSitesSelected = [];
	for (let i = 0; i < sites.length; i++) {
		if (!sites[i].checked || sites[i].dataset.site == '100') {
			continue;
		}

		const data = sites[i].dataset;
		otherSitesSelected.push({
			site: data.site,
			siteName: data.siteName,
			userName: data.account,
			id: sites[i].value
		});
	}

	if (otherSitesSelected.length === 0) {
		document.querySelector('.twitter-link').classList.add('hidden');
		return;
	}

	document.querySelector('.twitter-links').innerHTML = '';

	const links = document.querySelector('.twitter-links');

	for (let i = 0; i < otherSitesSelected.length; i++) {
		let item = document.createElement('div');
		item.classList.add('radio');

		let checkbox = document.createElement('input');
		checkbox.type = 'radio';
		checkbox.value = otherSitesSelected[i].id;
		checkbox.name = 'twitterlink';

		let label = document.createElement('label');
		label.appendChild(checkbox);
		label.innerHTML += ' ' + otherSitesSelected[i].siteName + ' - ' + otherSitesSelected[i].userName;

		item.appendChild(label);
		links.appendChild(item);
	}

	document.querySelector('.twitter-link').classList.remove('hidden');
};

updateTwitterLinks();

sites.forEach(site => site.addEventListener('change', updateTwitterLinks));

const insertUserLink = () => {
	$('.add-user-modal').modal('hide');

	const values = [
		document.querySelector('.add-user-modal input[name="username"]').value,
		document.querySelector('.add-user-modal input[name="site_name"]:checked').value,
		document.querySelector('.add-user-modal input[name="link_type"]:checked').value
	];

	const output = '<|' + values.join(',') + '|>';

	const textArea = document.querySelector('textarea[name="description"]');

	const caretPos = textArea.selectionStart;
	textArea.value = textArea.value.substring(0, caretPos) + output + textArea.value.substring(caretPos);

	document.querySelector('.add-user-modal input[name="username"]').value = '';
};

$('.description-preview-modal').on('show.bs.modal', function () {
	var body = document.querySelector('.description-preview-modal .modal-body');
	body.innerHTML = 'Loading&hellip;';

	$.ajax({
		type: 'GET',
		url: '/preview/description',
		data: $('input[name="account"], .description').serialize()
	}).always(function (data) {
		body.innerHTML = '';

		for (var i = 0; i < data.descriptions.length; i++) {
			var description = data.descriptions[i];

			var name = document.createElement('label');
			name.innerHTML = description.site;

			var well = document.createElement('div');
			well.classList.add('well');

			$(well).text(description.description);

			body.appendChild(name);
			body.appendChild(well);
		}
	});
});

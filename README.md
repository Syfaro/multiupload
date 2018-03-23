# Installation

Create a virtualenv:

~~~sh
virtualenv venv
~~~

Activate the virtualenv:

~~~sh
. venv/bin/activate
~~~

Install the necessary dependencies:

~~~sh
pip install -r requirements.txt
~~~

Generate a config file:

~~~sh
python generate_config.py >src/config.py
~~~

Customize it as necessary.

Migrate databases:

~~~sh
FLASK_APP=src/art.py ./venv/bin/flask db upgrade
~~~

Run it:

~~~sh
python src/art.py
~~~

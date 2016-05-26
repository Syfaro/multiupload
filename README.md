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
python generate_config.py >config.py
~~~

Run it:

~~~sh
python art.py
~~~

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

Customize it as necessary.

Create the database.  For development purposes, SQLite3 will do:

~~~sh
sqlite3 <db.sql test.db
~~~

Run it:

~~~sh
python art.py
~~~

Q: How to deploy Insights API on a new server?

A: Ask ITS to deploy Insights API on the new server

According to ITS, these are the steps they take:

```
#!bash

git clone git@bitbucket.org:dfeinleib/tmtext.git
place config file
docker login registry.contentanalyticsinc.com
docker run -d -v /var/web/tmtext:/var/web/tmtext --name insights_api registry.contentanalyticsinc.com/ch-scrapers/insights-api
run migrations from container ( docker exec -it insights_api bash )
```

Additionally, the following migrations may need to be run:


```
#!bash

python manage.py migrate
python manage.py create_dummy_user
```

---------------------------------------------------------

# The following instructions are old and are for reference only #

Clone tmtext repository into /var/web/tmtext

```
#!bash

cd /var/web
git clone https://<username>@bitbucket.org/dfeinleib/tmtext.git
```

Path to the api folder

```
#!bash
path="/var/web/tmtext/insights_api"
```

Install dependences

```
#!bash

sudo apt-get update
sudo apt-get install python-dev, python-pip, python-virtualenv, uwsgi
```

```
#!bash
cd $path
```

Create virtual env

```
#!bash

virtualenv venv
source venv/bin/activate
pip install -r requirements.txt
```


Change any necessary DB settings in insights_api/settings.py

```
#!text

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'c38trillionmonkeys_com',
        'USER': 'root',
        'PASSWORD': 'L4f12v23Nh49IB8',
        'HOST': '127.0.0.1',
        'PORT': '5432',
    }
}
```


Update DB tables to support Django api

```
#!bash

python manage.py makemigrations
python manage.py migrate
```

Copy static files to local dir

```
#!bash
python manage.py collectstatic
```

Create root user

```
#!bash
python manage.py createsuperuser
```

Create dummy user

```
#!bash
python manage.py create_dummy_user
```


Configure UWSGI

```
#!bash

sudo mkdir -p /etc/uwsgi/sites
cd /etc/uwsgi/sites
sudo nano insights_api.ini
```

```
#!text

[uwsgi]
project = insights_api
base = /home/victorruiz/tmtext/insights_api

chdir = %(base)/
home = %(base)/venv/
module = %(project).wsgi:application
master = true
processes = 5
socket = %(base)/%(project).sock
chmod-socket = 664
uid = www-data
gid = www-data
chown-socket=www-data:www-data
vacuum = true
```

```
#!bash
sudo nano /etc/init/uwsgi.conf
```

```
#!text

description "uWSGI application server in Emperor mode"

start on runlevel [2345]
stop on runlevel [!2345]
exec /usr/local/bin/uwsgi --emperor /etc/uwsgi/sites
```


Install and configure nginx (if needed)

```
#!bash

sudo apt-get install nginx
sudo nano /etc/nginx/sites-available/insights_api
```

```
#!text

server {
    listen 80;
     server_name victor-test.contentanalyticsinc.com www.victor-test.contentanalyticsinc.com;  ~ <- Configure with your dns name

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
         root /home/victorruiz/tmtext/insights_api;                                      ~ <- Configure with your $path
    }

    location / {
        include         uwsgi_params;
         uwsgi_pass      unix:/home/victorruiz/tmtext/insights_api/insights_api.sock;    ~ <- Configure with your $path
    }

    access_log /var/log/nginx/insights_api-access.log;
    error_log /var/log/nginx/insights_api-error.log;
}
```


```
#!bash
sudo ln -s /etc/nginx/sites-available/insights_api /etc/nginx/sites-enabled/
```

Test the Configuration
```
#!bash
sudo service nginx configtest
```

If everything is right, restart
```
#!bash
sudo service nginx restart
```

Start uwsgi
```
#!bash
sudo service uwsgi restart
```
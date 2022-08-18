sudo apt-get update

echo "# Installing general dependencies..."
sudo apt-get install -y nginx
sudo apt-get install -y libpq-dev
sudo apt-get install -y supervisor lib32z1-dev virtualenvwrapper
sudo apt-get install -y libffi-dev libssl-dev build-essential
sudo apt-get install -y libxml2-dev libxslt1-dev python-dev python-lxml

echo "# Installing MongoDB dependencies..."
sudo apt-get install -y mongodb

echo "# Creating root dir..."
ROOT_DIR="/var/web"
sudo mkdir $ROOT_DIR
sudo chmod 777 $ROOT_DIR

echo "# Creating log dirs..."
mkdir $ROOT_DIR/logs
mkdir $ROOT_DIR/logs/nginx

echo "# Activating virtual environment..."
virtualenv $ROOT_DIR/tmtextenv
source $ROOT_DIR/tmtextenv/bin/activate

echo "# Clonning repo in root dir..."
git clone https://bitbucket.org/dfeinleib/tmtext.git $ROOT_DIR/tmtext

echo "# Installing requirements..."
pip install -r $ROOT_DIR/tmtext/review_api/requirements.txt

echo "# Adding Nginx config..."
sudo tee /etc/nginx/sites-available/review_api <<EOF
server {
    listen      80 default_server;
    server_name _;
    charset     utf-8;
    client_max_body_size 75M;

    access_log $ROOT_DIR/logs/nginx/access.log;
    error_log $ROOT_DIR/logs/nginx/error.log;

    location /favicon.ico {
        access_log off;
        log_not_found off;
    }

    location /static {
        alias $ROOT_DIR/tmtext/review_api/app/static;
    }

    location / {
        include uwsgi_params;
        uwsgi_pass 127.0.0.1:8000;
    }
}
EOF

sudo rm /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/review_api /etc/nginx/sites-enabled/review_api
sudo service nginx restart

echo "# Adding Uwsgi config..."

sudo tee $ROOT_DIR/tmtext/review_api/app.ini <<EOF
[uwsgi]
socket = 127.0.0.1:8000
chmod-socket = 664
uid = www-data
gid = www-data

chdir = $ROOT_DIR/tmtext/review_api
virtualenv = $ROOT_DIR/tmtextenv
home = $ROOT_DIR/tmtextenv
wsgi-file = $ROOT_DIR/tmtext/review_api/wsgi.py

master = true
processes = 4
threads = 2
harakiri = 60

buffer-size = 32768
die-on-term = true
vacuum = true

lazy-apps = true

EOF

echo "# Adding Supervisor config..."

sudo tee /etc/supervisor/conf.d/review_api.conf <<EOF
[program:review_api]
environment=PATH="$ROOT_DIR/tmtextenv/bin"
directory = $ROOT_DIR/tmtext/review_api
user = www-data
command = $ROOT_DIR/tmtextenv/bin/uwsgi app.ini
redirect_stderr=true
stderr_logfile = $ROOT_DIR/logs/review_api.err.log
stdout_logfile = $ROOT_DIR/logs/review_api.log
stdout_logfile_maxbytes = 100MB
stdout_logfile_backups=30
autostart = true
autorestart = true
killasgroup = true
stopasgroup = true
stopsignal = INT

EOF

sudo tee /etc/supervisor/conf.d/review_crawler.conf <<EOF
[program:review_crawler]
environment=PATH="$ROOT_DIR/tmtextenv/bin"
directory = $ROOT_DIR/tmtext/review_api
user = www-data
command = $ROOT_DIR/tmtextenv/bin/celery -A app.crawler.celery worker --concurrency=5 -B -s /var/tmp/celerybeat-schedule
redirect_stderr=true
stderr_logfile = $ROOT_DIR/logs/review_crawler.err.log
stdout_logfile = $ROOT_DIR/logs/review_crawler.log
stdout_logfile_maxbytes = 100MB
stdout_logfile_backups=30
autostart = true
autorestart = true
killasgroup = true
stopasgroup = true
stopsignal = INT
stopwaitsecs = 3600

EOF

sudo service supervisor restart

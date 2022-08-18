sudo apt-get update

echo "# Installing general dependencies..."
sudo apt-get install -y nginx
sudo apt-get install -y libpq-dev
sudo apt-get install -y supervisor lib32z1-dev virtualenvwrapper
sudo apt-get install -y libffi-dev libssl-dev build-essential
sudo apt-get install -y libxml2-dev libxslt1-dev python-dev python-lxml

echo "# Installing PostgreSQL dependencies..."
sudo apt-get install -y postgresql postgresql-client postgresql-contrib

echo "# Creating new database..."
sudo su postgres -c psql template1 << EOF
ALTER USER postgres WITH PASSWORD 'password';
EOF
sudo su postgres -c "createdb sitemap_service"

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
pip install -r $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service/requirements.txt

echo "# Adding Nginx config..."
sudo tee /etc/nginx/sites-available/sitemap_service <<EOF
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
        alias $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service/app/static;
    }

    location / {
        include uwsgi_params;
        uwsgi_pass 127.0.0.1:8000;
        uwsgi_max_temp_file_size 2048m;
    }
}
EOF

sudo rm /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/sitemap_service /etc/nginx/sites-enabled/sitemap_service
sudo service nginx restart

echo "# Adding Uwsgi config..."

sudo tee $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service/app.ini <<EOF
[uwsgi]
socket = 127.0.0.1:8000
chmod-socket = 664
uid = www-data
gid = www-data

chdir = $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service
virtualenv = $ROOT_DIR/tmtextenv
home = $ROOT_DIR/tmtextenv
wsgi-file = $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service/wsgi.py

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

sudo tee /etc/supervisor/conf.d/sitemap_service.conf <<EOF
[program:sitemap_service]
environment=PATH="$ROOT_DIR/tmtextenv/bin"
directory = $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service
user = www-data
command = $ROOT_DIR/tmtextenv/bin/uwsgi app.ini
redirect_stderr=true
stderr_logfile = $ROOT_DIR/logs/sitemap_service.err.log
stdout_logfile = $ROOT_DIR/logs/sitemap_service.log
stdout_logfile_maxbytes = 100MB
stdout_logfile_backups=30
autostart = true
autorestart = true
killasgroup = true
stopasgroup = true
stopsignal = INT

EOF

sudo tee /etc/supervisor/conf.d/sitemap_service_crawler.conf <<EOF
[program:sitemap_service_crawler]
environment=PATH="$ROOT_DIR/tmtextenv/bin"
directory = $ROOT_DIR/tmtext/sitemap_utilities/sitemap_service
user = www-data
command = $ROOT_DIR/tmtextenv/bin/celery -A app.crawler.celery worker -B -s /var/tmp/celerybeat-schedule
redirect_stderr=true
stderr_logfile = $ROOT_DIR/logs/sitemap_service_crawler.err.log
stdout_logfile = $ROOT_DIR/logs/sitemap_service_crawler.log
stdout_logfile_maxbytes = 100MB
stdout_logfile_backups=30
autostart = true
autorestart = true
killasgroup = true
stopasgroup = true
stopsignal = INT

EOF

sudo service supervisor restart

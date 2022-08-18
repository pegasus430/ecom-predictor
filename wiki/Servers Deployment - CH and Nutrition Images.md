This wiki contains the setup for servers running some web services - this setup is used for the content health scraper servers and for the nutrition images service.

The service is built using **flask**, and deployed with **uwsgi** and **nginx**.

The code repository is cloned in `/home/ubuntu/tmtext` and the service runs inside a virtual environment in `/home/ubuntu/tmtextenv`.

# uwsgi configuration

The configuration file for uwsgi can be found in `/etc/flask-uwsgi/flask-uwsgi.ini`, these are its contents:

    [uwsgi]
    socket = 127.0.0.1:8001
    chmod-socket = 644
    chdir = /home/ubuntu/tmtext/<service_dir>
    wsgi-file = /home/ubuntu/tmtext/<service_dir>/<service_file>
    virtualenv = /home/ubuntu/tmtextenv
    home = /home/ubuntu/tmtextenv
    callable = app
    ; master = true
    ; www-data uid/gid
    uid = 33
    gid = 33
    die-on-term = true
    processes = 4
    threads = 2
    logger = file:/var/log/flask-uwsgi/flask-uwsgi.log

The variables are the service directory and service file, they should be replaced in fhe config file with their actual values, different for the CH service and the nutrition images service:

- CH service:
    - `<service_dir>` : `special_crawler`
    - `<service_file>` : `crawler_service.py`

- Nutrition images service:
    - `<service_dir>` : `nutrition_info_images`
    - `<service_file>` : `nutrition_images_service`

For the nutrition service, the following line was added to the configuration file to allow for GET parameters longer than 4096 bytes:

    buffer-size=32768


The logs are sent to the log file at the following path: `/var/log/flask-uwsgi/flask-uwsgi.log`

## Start uwsgi on boot

Put a `flask-uwsgi.conf` in `/etc/init`, with these contents:

    start on [2345]
    stop on [06]

    script
        cd /home/ubuntu/tmtext/special_crawler
        exec uwsgi --ini /etc/flask-uwsgi/flask-uwsgi.ini
    end script


# nginx configuration

Site for the service - configuration can be found in `/etc/nginx/sites-available/flask`:

    server {
        listen      80;
        server_name _;
        charset     utf-8;
        client_max_body_size 75M;

        location / { try_files $uri @flaskapp; }
        location @flaskapp {
            include uwsgi_params;
            uwsgi_pass 127.0.0.1:8001;
        }
    }

The service will listen on port 80.

# Pulling new code

Updates to the code are automatically pulled from the repository at boot time, by putting this code in `/etc/rc.local`:

    /usr/bin/sudo -u ubuntu /usr/bin/git --git-dir=/home/ubuntu/tmtext/.git --work-tree=/home/ubuntu/tmtext fetch
    /usr/bin/sudo -u ubuntu /usr/bin/git --git-dir=/home/ubuntu/tmtext/.git --work-tree=/home/ubuntu/tmtext checkout <branch>
    /usr/bin/sudo -u ubuntu /usr/bin/git --git-dir=/home/ubuntu/tmtext/.git --work-tree=/home/ubuntu/tmtext pull
    /usr/sbin/service flask-uwsgi start

`<branch>` should be replaced with the branch the production code should be pulled from.

Currently,

- `<branch>` = `production` for the CH service
- `<branch>` = `master` for the nutrition images service

For the CH servers which are part of an autoscale cluster and launched using the SQS queue, this line has to be added as well, to start the queue handler:

    /home/ubuntu/tmtext/special_crawler/queue_handler/start.sh



# AMIs

An AMI has been created from the current version of this server, and can be used to launch new such servers.

### Current AMIs

|          |                    CH servers                    | Nutrition image servers |
|----------|--------------------------------------------------|-------------------------|
| AMI id   | `ami-383f2a50`                                   | `ami-d927e9b2`          |
| AMI name | `CH-t2-autoscale-scraper-production_07052015_v2` | `nutrition_images_v1.0` |

# Dependencies

Dependencies for both these services can be found in their respective README and requirements files:

`tmtext/special_crawler/README.md`
`tmtext/special_crawler/requirements.txt`

`tmtext/nutrition_info_images/README.md`
`tmtext/nutrition_info_images/requirements.txt`

as well as the wiki pages:

https://bitbucket.org/dfeinleib/tmtext/wiki/Special%20crawler
https://bitbucket.org/dfeinleib/tmtext/wiki/Nutrition%20images%20service
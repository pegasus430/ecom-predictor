[TOC]

# How to update the code

* SSH into the server
 
* cd /home/ubuntu/tmtext/rest_apis_content_analytics
  
* killall gunicorn
  
* sudo -u ubuntu /bin/bash  /home/ubuntu/regression_console/start.sh
  
* make sure gunicorn is up and running by using "ps aux | grep gunicorn"
  
* check the site in browser

OLD OUTDATED DEPLOY STEPS BELOW - DO NOT USE IT! LEFT ONLY FOR REFERENCES!

How to restart the web server after you've updated the code:

```
sudo killall gunicorn
cd /home/ubuntu/tmtext/
git stash
git checkout master
git pull origin master
cd /home/ubuntu/tmtextenv/bin/
source activate
cd /home/ubuntu/tmtext/rest_apis_content_analytics/
python manage.py makemigrations
python manage.py migrate
cd /home/ubuntu/regression_console/
./start.sh
```


On master and production testing servers, authentication is required:

username: tester

password: /fO+oI7LfsA=


# To test a specific branch:

Log into the crawler machine. Then:

1\. Go to repo dir and checkout and pull branch

    $ cd /home/ubuntu/tmtext
    $ git checkout <branch>
    $ git pull origin <branch>


2\. Restart service

You can do this by restarting the uwsgi master process. It's not entirely trivial, but here's how to do it if needed:

List all uwsgi processes:

    $ ps xau | grep uwsgi
    www-data   961  0.0  3.4  88048 20564 ?        Ss   18:56   0:01 /usr/local/bin/uwsgi --ini /etc/flask-uwsgi/flask-uwsgi.ini 
    www-data  2147  0.0  2.8 162840 17352 ?        Sl   20:49   0:00 /usr/local/bin/uwsgi --ini /etc/flask-uwsgi/flask-uwsgi.ini
    www-data  2149  0.0  2.8 162840 17356 ?        Sl   20:49   0:00 /usr/local/bin/uwsgi --ini /etc/flask-uwsgi/flask-uwsgi.ini
    www-data  2150  0.0  4.3 167080 26552 ?        Sl   20:49   0:00 /usr/local/bin/uwsgi --ini /etc/flask-uwsgi/flask-uwsgi.ini
    www-data  2153  0.0  5.8 176448 35428 ?        Sl   20:49   0:06 /usr/local/bin/uwsgi --ini /etc/flask-uwsgi/flask-uwsgi.ini
    ubuntu    2703  0.0  0.1   8104   932 pts/0    S+   22:46   0:00 grep --color=auto uwsgi

You can see some processes started by the `www-data` user.

We need to restart the master one.

Look for the one with `Ss` in the `STAT` column (here it's the first one), get its PID (second column) - here it's `961`, and send the `SIGHUP` signal to restart it:

    $ sudo kill -SIGHUP 961

OR trivial way: sudo service flask-uwsgi restart

# Automated branch testing

This process outlined above is automated on the master test server via manage_service.py. Visit [master-test-server]:8080/switch_branch and select the branch you wish to test. The branch must be local, so it will have to be checked out manually on the machine at least once beforehand.

# Normal Deploy

See: [Web Runner, Scrapyd, Product Ranking and others Deploy Procedure](Web Runner, Scrapyd, Product Ranking and others Deploy Procedure)
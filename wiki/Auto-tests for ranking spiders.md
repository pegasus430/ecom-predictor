** THIS IS OBSOLETE, A NEW WIKI PAGE IS COMING SOON **

# **Main concept and goal:** 
This auto-tests for ranking spiders, automatically checks the scrapers(walmart, amazon, amazon.co.uk, etc) and send report emails to Content Analytics Team if any scraper issues occurred.
This is a daily cronjob and runs at once a day.


##How it works?##

Every spider supports `-validate=1` command-line arg. In this mode, special code will catch the "on_close" spider event, and will validate the output using pre-defined rules.

### Current setup ###

You can change the cronjob settings by editing crontab file.

*$ sudo nano /etc/cron.d/auto_test_page_ranking
*

*00 09,21  * * *     root    /home/web_runner/repos/tmtext/product-ranking/auto_test_spiders.sh
*

This setting means that the auto-tests will run at 09:00 and 21:00 twice a day.


## Spiders that are currently supported ##

walmart.com, amazon.com, amazon.co.uk


## Where the code located at? ##

The code is located at this bitbucket repository and the branch name is "products_ranking_auto_tests_forked_master".

https://bitbucket.org/dfeinleib/tmtext/


## Server IP & Credentials ##
It was deployed at 52.0.7.54 and you can access to the server via ssh.

*$ ssh ubuntu@52.0.7.54*

**Project source**: /home/web_runner/repos/tmtext

**Virtual environment path**: /home/web_runner/virtual-environments/scrapyd


Auto-tests send report emails to 'Content Analytics Support Team - <support@contentanalyticsinc.com>'.


## How the codebase is going to be updated. ##
We should merge master branch to "products_ranking_auto_tests_forked_master" and then deploy this "products_ranking_auto_tests_forked_master" branch onto test server.


**New spiders to implement**
We can implement this auto-tests for other spiders.

amazon.ca

amazon.cn

amazon.co.jp

amazon.fr

fresh.amazon.com

bestbuy.co

maplin.co.uk

pgshop.com

quill.com

samsclub.com

soap.com

staples.com

staplesadvantage.com

target.com

tesco.com

tesco.com

...





## Here is an example report email content. ##

*[('description', ' | ROW: 2'), ('image_url', ' | ROW: 3'), ('price', 'Price(priceCurrency=USD, price=19.00) | ROW: 2'), ('title', 'Handbuch der Umweltver\xc3\xa4nderungen und \xc3\x96kotoxikologie: Band 1A: Atmosph\xc3\xa4re Anthropogene und biogene Emissionen Photochemie der Troposph\xc3\xa4re Chemie der Stratosph\xc3\xa4re und Ozonabbau (German Edition) | ROW: 4')]*


This means that "description" field of 2nd product in search result, is empty.

"image_url" field of 3nd product in search result, is empty.



## How to deploy to an auto-test server? ##


1) You need to install in your virtualenv - pip install Fabric cuisine ecdsa


2) And then you need to open tmtext/deploy/fabfile.py


3) Replace CERT_REPO_URL = 'git@bitbucket.org:dfeinleib/tmtext-ssh.git' with CERT_REPO_URL = 'git@bitbucket.org:dfeinleib/tmtext.git'


4) Run in console


*fab -H  52.0.7.54 set_production deploy:branch=products_ranking_auto_tests_forked_master,restart_scrapyd=True
*

It will work but suddenly will stop after that, you need to add in home/tmp/web_runner_ssh_keys/tmtext/ all your ssh keys which Andrey give you
and again run fab ...


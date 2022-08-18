# Table of contents
[TOC]

# Introduction 
This procedure explains how to deploy Web Runner REST API Server and other services used by Web Runner.

**WARNING! THIS PAGE IS OUTDATED! SEE https://bitbucket.org/dfeinleib/tmtext/wiki/SC%20and%20CH%20spiders%20deployment%20procedure for new deploy procedure!**

[Fabric](http://www.fabfile.org/) is the tool used for the deployment. It was created a custom Fabric file that handles the user creation, permissions, packages dependencies, virtual environment, etc. 



# High Level Deployment Workflow

The tasks that the deployment script does are:

    1. Setup user and groups. Generates SSH certificates
    2. Deploy all the required packages and 3rd party tools like git and tmux
    3. Setup the Python's virtual environment for each project
    4. Download the Web Runner files from BitBucket repo
    5. Install and configure Web Runner
    6. Run all services



# Requirements of the Target Server

    1. Target server should be accessed via ssh
    2. ubuntu user should exists and be accessed via SSH
    3. ubuntu user should have sudo without password
    4. ubuntu user should have below public certificate in SSH

[certificate](https://bitbucket.org/itsyndicate/tmtext-ssh/src/4d65baddc22230c8087f0347033437e8798098c7/ubuntu_id_rsa.pub?at=master)

# Requirements of the user that is going to deploy

    1. Have access the repository tmtext-ssh 
    2. The access to the repository must be with ssh certificates


# Requirements of the machine that runs the deployment script

1. Python 2.7
2. Python libraries Fabric and cuisine


    
# Fabric Commands

The Fabric script has several commands to execute all the workflow described above. Nevetheless, there are 2 main commands that contains all the functionallity to make the deployment:

*   *set_production*: tells to fabric to deploy in production environment
*   *deploy*: deploy or update everything

There are another usefull commands to performe partial deployment:

*   *deploy_scrapyd*: only deploys scrapyd and scrapyd-deploy
*   *deploy_web_runner*: only deploys Web Runner REST Server
*   *deplot_web_runner_web*: only deploys the Web Runner Web Interface

# Testing

##For all testing actions:   

1.  cd tmtext/deploy/test
2.  In file fabric.py to set list of servers in variable "servers". Servers which you set will be checked. Example:  
```
#!python
    servers = [
                "keywords.contentanalyticsinc.com",
                "keywords2.contentanalyticsinc.com",
                "keywords3.contentanalyticsinc.com",
                 ...
            ]
```
##Test the server to see whether running spider:
1. fab is_servers_work
2. You will see the result in your console for every server and also you can see the result in error.txt file 

##Testing the servers after deploy::

1. fab test_servers
2. You will see the result in your console for every server and also you can see the result in servers.txt file. STATUS:
    * TESTS PASSED - all work normally
    * TESTS FAILED - spider not working
    * SCRIPT ERROR - maybe you have no permission, or it can be any other error in script.

##Checking that all servers have a single commit:

1. fab check_commits
2. You will see the result in your console for every server. Example: 

```
    DIFFERENCE: 
    f65b48594da6b486dc130ac7ba5b0885a6829950  -  keywords.contentanalyticsinc.com
    3e7c9a387788a6ae1c3ca9f4c52d86c831d697a4  -  keywords16.contentanalyticsinc.com

    WARRNING: SERVERS HAVE DIFFERENT COMMITS
```
or
```
    DIFFERENCE: 
    3e7c9a387788a6ae1c3ca9f4c52d86c831d697a4  -  keywords.contentanalyticsinc.com,
    keywords16.contentanalyticsinc.com, 
    keywords15.contentanalyticsinc.com, 
    keywords14.contentanalyticsinc.com 

    Servers have one commit
```

##Get not deployed commits

1. fab -H <server> set_production get_commits_diff
2. You will see the result in commits_diff.txt file.

# Deploy instructions

The high level instructions are:

    1. Install the packages and libraries to run the deployment script
    2. Download the repository with the deployment script and SSH certificates
    3. execute the deployment script

## Install deployment dependencies

```
gabo@gabo:~$ sudo apt-get install python2.7 python-virtualenv
gabo@gabo:~$ mkdir venv
gabo@gabo:~$ virtualenv -p python2.7 venv/web-runner-deploy
gabo@gabo:~$ source ~/venv/web-runner-deploy/bin/activate
(web-runner-deploy)gabo@gabo:~$ pip install Fabric cuisine ecdsa
```

## Get the deployment repo
```
(web-runner-deploy)gabo@gabo:~$ mkdir repos
(web-runner-deploy)gabo@gabo:~$ cd repos/
(web-runner-deploy)gabo@gabo:~/repos$ git clone https://bitbucket.org/dfeinleib/tmtext.git
(web-runner-deploy)gabo@gabo:~/repos$ cd tmtext/deploy/
```

## Run the Deployment Script
```
(web-runner-deploy)gabo@gabo:~/repos/tmtext/deploy$ fab -H <target_server> set_production deploy
```

# Upgrades

The deploy script supports upgrade feature. If the target server has an old version of one of the Web Runner components, the user can upgrade to the last one. The way to run the upgrade is exactly the same as the deploy is invoked the first time.

## Scrapyd restart

By default, after a Web Runner upgrade, new spiders and commands are deployed, but scrapyd is not restarted.  

If the user decides to restart scrapyd, the fabric's deploy command should be invoked with restart_scrapyd parameter with a True value.

```
(web-runner-deploy)gabo@gabo:~/repos/tmtext/deploy$ fab -H keywords2.contentanalyticsinc.com set_production deploy:restart_scrapyd=True
```

## Run commands from local file

```
fab exec_commands:file_name=cm.txt,serv_file=servers
```
1) file_name - file with commands. Example:
```
find /home/web_runner/virtual-environments/scrapyd/logs/product_ranking/  -type f -name "*.log"
cp -r /home/web_runner/virtual-environments/scrapyd/logs/product_ranking /mnt/
ln -s /home/web_runner/virtual-environments/scrapyd/logs/product_ranking /mnt/product_ranking
```
2) serv_file - file with remote server list. Example:
```
{"servers": [
	    "keywords.contentanalyticsinc.com",
	    "keywords2.contentanalyticsinc.com",
	    "keywords3.contentanalyticsinc.com",
             ..............
	]
}
```


# Deploying a Git Branch Different From Master

The user is able to deploy a git branch different from master. For that the user should call deploy with a branch parameter:

```
(web-runner-deploy)gabo@gabo:~/repos/tmtext/deploy$ fab -H keywords2.contentanalyticsinc.com set_production  deploy:branch=Iss82OperationalStatus
```

# Full Deploy Procedure with commands

I'll describe here how to deploy scrapy, scrapyd, web runner and others to keywords.contentanalyticsinc.com

## git commits and push
Initially we start with changes on the wip branch, we change, and finally we push.

1. Merge just the needed changes into master
1. Push to master **REMEMBER TO PULL/PUSH**
1. Clean any unwanted file:

        git clean -X -f
    (you may use ```--dry-run```  instead of ```-f``` to check)


Test on the master branch, just in case

## Deploy

```
cd ../deploy/

# FIRST TIME ONLY:  pyenv virtualenv 2.7.8 product-ranking-deploy

pyenv activate product-ranking-deploy

# FIRST TIME ONLY: pip install -r requirements.txt
```

Browse to: [http://keywords8.contentanalyticsinc.com:8000/simple_cli/status/](The keywords status page)

> *First Time only:* 
>
> If you are not using 'git@bitbucket.org:itsyndicate/tmtext-ssh.git', you need to clone the repo from where you have this repo accessible, for example:
> 
>     git clone git@bitbucket.org:dfeinleib/tmtext-ssh.git $HOME/tmp/web_runner_ssh_keys/tmtext-ssh
 

Then, with this command, you deploy to the server

```
fab set_production deploy:branch=master -H keywords8.contentanalyticsinc.com
```


Check on UI the deploy
> *First Time only:*
> 
>     chmod 700 $HOME/tmp/web_runner_ssh_keys/tmtext-ssh
>     chmod 600 $HOME/tmp/web_runner_ssh_keys/tmtext-ssh/*

Connect to the server

```
ssh -i $HOME/tmp/web_runner_ssh_keys/tmtext-ssh/web_runner_rsa web_runner@keywords8.contentanalyticsinc.com
```

Run the spider (this will run several spiders with different sorting and with a good priority to be executed before the normal ones) **replacing the site and the searchterms_str**

```
curl --verbose -L 'http://localhost:6543/ranking_data_with_best_sellers/' -d site=amazon -d 'searchterms_str=laundry detergent' -d quantity=20 -d priority=100
```

From there, copy the 302 header location (the one with the quotes is perfect) and run

```
curl -L 'XXX'   # where XXX is the location http header
```

Example (**do not use this one***): 

```
curl -L 'http://localhost:6543/command/with-best-seller/pending/eNprYIotZNCIUGBgYDBJSUszMEw1MjOxsDQ0TDWxSE4yMjQySNTZPLWSEKEs1MExONU3FqYwpVQ8AdpkVAw%3D%3D/?site=google&searchterms_str=laundry+detergent&quantity=20&priority=100'
```

Do a thorough test here, you might use the previous command, and check log files on

`virtual-environments/scrapyd/logs/product_ranking`

Or

```
tmux attach
``` 

Use `Ctrl+b d` to exit tmux console

**Important, don't close anything, don't stop anything on the tmux console**

To pretty print the output of the curl command (this will test just the line *1*:

```
source virtual-environments/scrapyd/bin/activate
curl -L 'XXX' | sed -n 1p | python -m json.tool | less
```


Once you have tested this server, continue with the rest:
```
fab set_production deploy:branch=master -H keywords.contentanalyticsinc.com,keywords2.contentanalyticsinc.com,keywords3.contentanalyticsinc.com,keywords4.contentanalyticsinc.com,keywords5.contentanalyticsinc.com,keywords6.contentanalyticsinc.com,keywords7.contentanalyticsinc.com,keywords9.contentanalyticsinc.com,keywords10.contentanalyticsinc.com,keywords11.contentanalyticsinc.com,keywords12.contentanalyticsinc.com,keywords13.contentanalyticsinc.com,keywords14.contentanalyticsinc.com,keywords15.contentanalyticsinc.com,keywords16.contentanalyticsinc.com
```

Perform the testing on every server, one useful command for it is:
```
for i in keywords.contentanalyticsinc.com keywords{2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}.contentanalyticsinc.com
do
  ssh -t -i $HOME/tmp/web_runner_ssh_keys/tmtext-ssh/web_runner_rsa web_runner@$i
done
```


## Communications

After everyting is deployed

1. Log into github
1. Create [New issue](https://github.com/ContentAnalytics/tmeditor/issues/new) there
1. Assign it to ruslushak
1. Fill into the issue description, what was deployed, and what has been changed.
1. If you need to comunicate anyone use `@dfeinleib`
    * Use this subject: New Spiders Deployed (YYY-MM-DD)
    * Specify there the python file name of the spider changing and the internal name
    * Add in your own words what is changing
1. Fill the [Spiders - written and deployed](https://docs.google.com/spreadsheets/d/1oH4Jm50uMfxbugFzByVAoHr4lqWrX8uaZ270vOLu2QE/edit#gid=1449963779) worksheet, maintaining the alphabetical order


# Testing on a Production-like Vagrant box

* Install [Vagrant](https://docs.vagrantup.com/v2/installation/index.html) with the normal procedure, you will need [VirtualBox](https://www.virtualbox.org/) installed as well
* Clone the repo [tmtext](git@bitbucket.org:dfeinleib/tmtext.git) (This step is not needed if you already have it)
* Go to the *deploy* directory ```cd deploy```
* Run ```vagrant up``` command
* Activate the environment as expressed in [Deploy](#markdown-header-deploy) section.
* Deploy the same way you use for prod, use this command:

        fab set_environment_vagrant deploy:branch=master -H keywords8.contentanalyticsinc.com

    It fails on first run after first vagrant up. Rerun on case of failure.

    As specified before, if you want to test on your own branch (i.e. named YOUROWNBRANCH, this branch should be present and up to date on bitbucket)

         fab set_environment_vagrant deploy:branch=YOUROWNBRANCH -H keywords8.contentanalyticsinc.com
       
    If it complains about not finding YOUROWNBRANCH and the branch *is* in the remote repo, go into the box:
        vagrant ssh
        sudo -u web_runner -i
        cd repos/tmtext
        git pull --all

* Finally to connect to the server do:

        vagrant ssh
        sudo -u web_runner -i

    test and use it the same way as in [Detailed Deploy Procedure](#markdown-header-detailed-deploy-procedure) with ```curl```, ```tmux``` and others. 


# pdsh Usage

Pdsh is a parallel ssh. It can be used with the help of dshbak (comes with pdsh) for a lot of interactions/searching/grepping with the servers.

* First install pdsh, you should probably have it on your OS repo

* Generate the groups

```
cat > ~/.dsh/group/cakeywords <<EOF
keywords.contentanalyticsinc.com
keywords2.contentanalyticsinc.com
keywords3.contentanalyticsinc.com
keywords4.contentanalyticsinc.com
keywords5.contentanalyticsinc.com
keywords6.contentanalyticsinc.com
keywords7.contentanalyticsinc.com
keywords8.contentanalyticsinc.com
keywords9.contentanalyticsinc.com
keywords10.contentanalyticsinc.com
keywords11.contentanalyticsinc.com
keywords12.contentanalyticsinc.com
keywords13.contentanalyticsinc.com
keywords14.contentanalyticsinc.com
keywords15.contentanalyticsinc.com
keywords16.contentanalyticsinc.com
EOF
```

* Generate the ssh configs (for the keys and users) (backup your .ssh/config before, just in case)
```
cat >> ~/.ssh/config <<EOF

Host keywords.contentanalyticsinc.com keywords2.contentanalyticsinc.com keywords3.contentanalyticsinc.com keywords4.contentanalyticsinc.com keywords5.contentanalyticsinc.com keywords6.contentanalyticsinc.com keywords7.contentanalyticsinc.com keywords8.contentanalyticsinc.com keywords9.contentanalyticsinc.com keywords10.contentanalyticsinc.com keywords11.contentanalyticsinc.com keywords12.contentanalyticsinc.com keywords13.contentanalyticsinc.com keywords14.contentanalyticsinc.com keywords15.contentanalyticsinc.com keywords16.contentanalyticsinc.com
	User web_runner
	IdentityFile ~/tmp/web_runner_ssh_keys/tmtext-ssh/web_runner_rsa

EOF
```

* Use it, for example

```
pdsh -g cakeywords date | dshbak -c
```

# Parallel (simplified) deploy

## Deployment

There is a script called `parallel_deploy.sh` in the `/deploy` dir. Just run it and answer `y` when you are asked. Be careful - after that, it will re-deploy the code across all 16 servers.

Execute it, wait until everything successfully stops, click Enter if needed (to get back to the shell input). Repeat 2 times. Why? Because sometimes Scrapyd does not restart, and there is a chance you'll have an outdated code somewhere. Not sure about the reason - just re-execute the parallel_deploy.sh script 2 more times and everything will be ok.

In some cases, you have to deploy only to 5-6 servers at once. For that, comment out all the others in the fabfile.py file. They are separated into 5 or 6 groups already. So you have to deploy one group twice, then comment this group, uncomment the next and deploy the next group etc. It's probably because bitbucket fails to provide the files, but the real reason is unknown.

## Testing Scrapyd

After deployment, log into 3 randomly chosen servers and test them. For that, execute curl:

```
curl --verbose -L http://localhost:6543/ranking_data/  -d 'site=walmart;searchterms_str=batteries;quantity=20'
```

OR 
```
curl --verbose -L http://localhost:6543/ranking_data/  -d 'site=amazon;searchterms_str=batteries;quantity=20'
```

You'll see a curl output with a url like 
```
http://localhost:6543/crawl/project/product_ranking/spider/walmart_products/job/036b87d8f5c311e4928212f18ee7878b/
```

(the last alphanumeric param should be different in your case; this is a job id).

wait a few minutes and try to run wget on this URL, like this:

```
wget  http://localhost:6543/crawl/project/product_ranking/spider/walmart_products/job/317cae26f4ca11e4928212f18ee7878b/ -O /tmp/1.jl
```

(make sure there is no /tmp/1.jl file before executing wget!)

Then, check the file /tmp/1.jl - it should contain 20 lines, each line is a JSON object with the data scraped. Depending on your needs, you may continue validating every line, or (if your goal is just to make sure the whole deployment process went fine) proceed next.

## Testing that every server restarted

Now, go to EVERY server listed in parallel_deploy.sh file. Urls are like this:

```
http://keywords.contentanalyticsinc.com:8000/simple_cli/status/
http://keywords2.contentanalyticsinc.com:8000/simple_cli/status/
http://keywords3.contentanalyticsinc.com:8000/simple_cli/status/
...
```

(just open them in a browser)

Password is admin / Content.

You'll see a colored disc in the top of the page, this disc should not contain a number that is LESS than 20. This is the number of the jobs. If Scrapyd on this server has just been restarted, it should not contain more than 20 jobs in the history. If it contains more, then the deployment process failed for this particular server and you should investigate why.

If you don't see any colored disc, it's okay as well - it means there are no jobs in the history at all.

Another thing you should see on these pages is the text

```
Web Runner Status: 
Scrapyd alive: True 
Scrapyd operational: True
Queue status: ok
```

If you have repeated this step for all the servers (currently, 16 + 1 PG server), and everything is fine, then the deployment process have been completed successfully.
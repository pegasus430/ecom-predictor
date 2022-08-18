Starting and stopping the launched Amazon instances:
=====================================================

(TODO)


Configuring the instances without Puppet
==========================================

Needed packages:

* git
* python-dev
* libxslt1-dev
* python-pip

Python packages:

* scrapy
* nltk

Nltk corpora:

* wordnet
* stopwords


Installation:

    sudo apt-get update

    sudo apt-get install git
    sudo apt-get install python-dev
    sudo apt-get install libxslt1-dev
    sudo apt-get install python-pip

    sudo pip install scrapy
    sudo pip install nltk

    python -m nltk.downloader wordnet
    python -m nltk.downloader stopwords


Launching 10 Amazon instances with Vagrant and configuring with Puppet
========================================================================
*(Not needed for interacting with the existing Amazon instances)*

You can use the instructions below to launch and manage 10 Amazon instances equipped to run a scrapy crawler and to push/pull code to/from the tmtext repo.


### Prerequisites: ###

This setup uses [vagrant-aws](https://github.com/mitchellh/vagrant-aws) (a plugin for [vagrant](http://www.vagrantup.com/)) for managing the machines, and [puppet](http://puppetlabs.com/) for automatically configuring them.

Install vagrant, vagrant-aws, and puppet on your machine:

    sudo apt-get install vagrant
    vagrant plugin install vagrant-aws
    vagrant box add aws001 https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box
    sudo apt-get install puppet


### Setting up the machines ###
Using aws_config to create, manage and configure 10 instances:


    cd aws_config

* **ssh keys**

Before creating the machines you'll need a pair of ssh keys in the aws_config/modules/common/files directory; you can generate them with: 

    cd modules/common/files
    ssh-keygen

(Leave passphrase blank). These keys will identify the machines. (the public key must be added to a user with access to the tmtext repo to be able to clone and fetch from it)

* **nltk data**

For running the crawler, you'll also need 2 nltk corpora downloaded in aws_config/nltk_data (this folder with be synced between the instances). Download the "wordnet" and the "stopwords" corpora on your local machine using `python -m nltk.downloader wordnet; python -m nltk.downloader stopwords`, then copy the /home/<username>/nltk_data directory into aws_config.

Alternatively, directly download the corpora on to each machine by logging into it and running the command above (`python -m nltk.downloader wordnet; python -m nltk.downloader stopwords`).

* **Start (create) the machines:**

    `vagrant up --provider=aws`

* **Install puppet on the machines and set their hostsname to be identifiable by puppet:**

    `./preconfigure.sh`

* **Configure the machines (install needed packages, create ssh keys files, clone tmtext repo etc):**

    `vagrant provision`

* **Add startup script**

Add following line to /etc/rc.local:

    /home/ubuntu/startup_script.sh



### Managing the machines ###

* Start instance:
   
    `vagrant up node1`

* Stop instance:

    `vagrant halt node1`

* Terminate instance:

    `vagrant destroy node1`

* Reconfigure instance:

    `vagrant provision node1`

* Ssh into an instance:

    `vagrant ssh node1`

* Similarly, start/stop/destroy/provision all instances:

    `vagrant up`

    `vagrant halt`

    `vagrant destroy -f`

    `vagrant provision`


AMI
=================

An AMI was created from a machine with this setup, under the contentanalytics aws account - the image named Distributed-crawler-node-tmtext, ID ami-6709360e
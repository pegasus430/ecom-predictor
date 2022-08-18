|Product matching runs distributedly on 10 AWS instances.

They are managed from a central server using:

- vagrant
- puppet
- sshfs for sharing input/output data
- bash scripts in `tmtext/aws_config`

# Central master server

This is the server that can control the 10 matching instances, it should not be necessary to log into any of the other 10 machines except for debugging purposes.

The server is already set up to control the 10 matching nodes, the instructions for setting up such a server can be found under the "Master server setup" heading below.

|             |                  |
|-------------|------------------|
| **IP**      | 52.5.176.21      |
| **Name**    | Matching-master  |
| **SSH key** | ana_matching.pem |


# Managing the 10 matching instances and running the matching process

For running product mathcing on any batch of input products, these are the steps:

## 0. Log into the server

ssh into the master server using the ana_matching.pem key.

    $ ssh -i ana_matching.pem ubuntu@52.5.176.21

## 1. Starting the 10 nodes

The 10 instances are stopped when they are not used, before running matching they have to be started, using vagrant:

    $ cd ~/tmtext/aws_config
    $ vagrant up

## 2. Setting up the shared folder

Any time the machines are started, the shared folder with the input and output files has to be set up using the following scripts:

    $ cd ~/tmtext/aws_config

Create the connection between the matching nodes and the master server:

    $ ./setup_local_sshfs.sh

Create the connection between the matching nodes (nodes 2 to 10 will connect to node 1):

    $ ./setup_sshfs.sh {2..10}

The shared directory that will contain the input and output files is

    ~/tmtext/aws_config/shared_sshfs

After running step 2, this will be shared among the master server and all the matching nodes.

## 3. Preparing the input files

Before starting the matching process, the input files containing the batch of urls to run matching for needs to be in the shared directory (`shared_sshfs`), split into 10 files, each containing a 10th of the batch.

To split the file into 10 equal parts and put them in the shared folder, this can be used:

    $ cd ~/tmtext/aws_config
    $ ../split_urls_file.py -f <input_csv> -s <number_of_urls_per_result_file>

For example, if the input batch has 1000 urls, 10 files each with a 10th of the input (100 urls) can be generated like this:

    $ ../split_urls_file.py -f input.csv -s 100

The resulted files (`input_<nr>.csv`) have to be moved to the `shared_sshfs` directory.

## 4. Starting the matching process

Now we are ready to run the matching.

First, lines 3 and 4 of `~/aws_config/run_all_crawlers.sh` need to be changed to point to the current batch we want to match:

- `INPUT`: the name of the input csv (without the extension, will be assumed it's `.csv`
- `SITE`: the target site to run matching against

For example, for `walmart_laptops.csv` matched against bestbuy.com:

    INPUT="walmart_laptops"
    SITE="bestbuy"

Then the script can be run and it will start matching using the 10 instances:
        
    $ cd ~/tmtext/aws_config
    $ ./run_all_crawlers.sh {1..10}

## 5. Collecting results

After the matching process is completed, the results files will be found in `shared_sshfs`, with names like `<input>_<target_site>_<node_nr>_matches.csv`.

While the matching process is still running, these files will contain partial output.

Collect the results in `shared_sshfs` into one file, and that will be the matching input.

## 6. Output types

By default, the output format is

    Original_URL,Match_URL,Confidence_score

The output type is specified in the `./run_crawler.sh` script that calls the scrapy crawlers, the `output` parameter.

The output types are:

    output - integer(1/2/3/4) option indicating output type (either result URL (1), or result URL and source product URL (2))
                             3 - same as 2 but with extra field representing confidence score
                             4 - same as 3 but with origin products represented by UPC instead of URL

## 7. Monitoring status

For monitoring the status of the 10 instances, a bash script can be used, that receives as parameter the name of the input batch and the target site. For example for input `walmart_laptops.csv` and target site `bestbuy.com`, the parameter will be `walmart_laptops_bestbuy`. On the master server, run:

    $ cd ~/tmtext/aws_config
    $ ./monitor-tmux.sh <input>_<target_site>

This will open a window split into several panels, containing, for each matching node:

- number of input urls processed so far ("RESULTS")
- number of matches found so far ("MATCHES")
- number of errors encountered (not very serious, a few errors do not mean process has failed) ("ERRORS")
- number of exceptions encountered (if there is any exception the process probably failed and needs to be restarted) ("EXCEPTIONS")

When the process is done for a node, the machine will automatically close (except for node 1). To check status of a machine, you can run:

    $ cd ~/tmtext/aws_config
    $ vagrant status node<nr>

If the node is `stopped` (and not `runnning`), it means either the matching process was finished or an exception was encountered and it was closed prematurely.

# Master server setup

The details on how the master server was configured:

The following packages need to be installed:

- git
    `$ sudo apt-get install git`
- vagrant
    - download linux package from  https://www.vagrantup.com/downloads.html and install with `$ sudo dpkg -i <package_name>`
    - install vagrant-aws plugin
        `$ vagrant plugin install vagrant-aws`
    - add vagrant box
        `$ vagrant box add aws001 https://github.com/mitchellh/vagrant-aws/raw/master/dummy.box`
- sshfs
    `$ sudo apt-get install sshfs`

The following files are assumed to be present on the server:

- key to access the 10 AWS instances in `~/.ssh`: in this case `Ana.pem`
- `nltk_data` directory in `/home/ubuntu`, get it by:
    - installing nltk: `$ pip install nltk`
    - download 2 needed corpora:
        `$ python -m nltk.downloader wordnet`
        `$ python -m nltk.downloader stopwords`
- empty `shared_sshfs` directory in `~/tmtext/aws_config`
- `run_crawler.sh` from `~/tmtext/aws_config` needs to be in the shared directory `shared_sshfs`

# Creating the 10 matching instances

The 10 nodes used for matching are already created and ready for use, the details on how they were created and set up can be found here:

https://bitbucket.org/dfeinleib/tmtext/wiki/Launching%20and%20managing%20AWS%20instances

# Product matching general details

General info on the product matching crawlers, their purpose and how they work can be found here:

https://bitbucket.org/dfeinleib/tmtext/wiki/Product%20matching%20(search%20crawler)
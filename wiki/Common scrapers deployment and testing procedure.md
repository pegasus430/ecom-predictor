# Introduction #
## How it works: ##
1. The new common scrapers uses *runner.py* script in the root of repo to start crawling process;
2. It pulls sqs-messages from the ingoing queue, parses and resolves body;
3. Messages passes into appropriate spider and crawling process goes as usual;
4. On *success* result scrapy pipeline (s3exporter.py) uploads jsonline file to s3 bucket;
5. On *success* *runner.py* sends *success* or *failure* message into outgoing queue to signalize UI about results;
6. If ingoing queue is not empty *runner.py* repeats from 2.

## How to test new scrapers using SQS-TOOLS ##
1. Go to http://sqs-tools.contentanalyticsinc.com/admin/gui/job/add/
2. For Walmart.com URLs, select "walmart_products" for Spider field
3. Enter the product URL in the "Product url" field
4. At the bottom, switch "Priority:" from "qa_test" to "new_scrapers"
5. After that, everything is the same as old scrapers, including testing on branch.
6. [Output](http://sqs-tools.contentanalyticsinc.com/admin/gui/job/) will be in the "Admin link to csv data file" column, but in json (.jl) format instead of csv.
You can use any json reader to pretty-print the data, for example [http://jsoneditoronline.org/](http://jsoneditoronline.org/) (paste the data to the left panel, press >)

There are some screenshots at bottom of this page for reference.

## How to enable new scraper on a specific server (PHP)
Uncomment the following lines in config.local.php:

CH format  
$config['sqs_queue_new'] = 'scraper_walmart_in';  
$config['new_arch_scrapers'] = ['walmart'];  
  
SC format  
$config['sqs']['new_arch_scrapers'] = ['walmart'];  


Reference: [IT-29423](https://contentanalytics.atlassian.net/browse/IT-29423)

## How to verify new scraper(s) are running
1. In Kibana, click on Discover on the left  

http://kibana-es1.contentanalyticsinc.com  
admin  
C8mH5SWbQT  
2. Choose the index "scrapers-*" (gray drop-down near upper-left)  
3. Type this in the search box at the top: server_hostname=dave-test (or whatever server name you entered above for the sqs job)  
4. You should see the log for your job (after it completes)  

## Branches in the repo ##
The *master* a branch is default branch in the repo which stores latest properly working code, but not tested and should NOT be deployed. This branch uses for QA testing.
The *production* branch is a branch in the repo which stores code which was completely tested, reviewed and deployed. Anything shouldn't be pushed or merged to the branch directly except normal deploying process.
Another branches should be removed from the repo after success pull request.

# Deploy #
## Local environment preparation ##
Need to setup kubectl utility and add access keys.
Please check [wiki article](https://bitbucket.org/dfeinleib/tmtext/wiki/Scrapers%20infrastructure), section "Configure kubectl".

1. Changes were deployed into *production* branch.
2. Get currently running pods:
   ```
   kubectl -n scraper get po -o wide -a
   ```
3. Need to force restart of kubernates pods for the *production* branch (in future job should be *general* instead of *walmart*):
   ```
   kubectl -n scraper delete job walmart
   ```
4. All pods will be terminated and recreate with changes on production branch.

In general, to restart production pods just need to delete task by name and pods will be recreated automatically.

## Additional work items
1. Use Jenkins to deploy - ~~[CON-38562](https://contentanalytics.atlassian.net/browse/CON-38562)~~
2. CSV output for new scrapers in sqs-tools (not just json) - [CON-38814](https://contentanalytics.atlassian.net/browse/CON-38814)
3. System UI support for turning new scrapers on/off for specific scraper - [CON-38658](https://contentanalytics.atlassian.net/browse/CON-38658)

## Jenkins

Any push to github repository production branch will be deployed and used by kubernetes job automatically.

## Initial servers that will be moved to Walmart new scraper

## Reference Screenshots

sqs-tools- 

![Screen Shot 2018-01-21 at 5.44.59 PM.png](https://bitbucket.org/repo/e5zMdB/images/4191479139-Screen%20Shot%202018-01-21%20at%205.44.59%20PM.png)

![Screen Shot 2018-01-21 at 5.45.06 PM.png](https://bitbucket.org/repo/e5zMdB/images/371122822-Screen%20Shot%202018-01-21%20at%205.45.06%20PM.png)


Kibana - 

![Screen Shot 2017-11-12 at 5.57.56 PM.png](https://bitbucket.org/repo/e5zMdB/images/1794314815-Screen%20Shot%202017-11-12%20at%205.57.56%20PM.png)
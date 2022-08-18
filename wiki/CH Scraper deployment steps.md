CH Scraper deployment steps

1) developer pushes the scraper into the ticket's branch and create pull request

2 PM(Andrey or me) reviews pull request and merge into master in the bitbucket after test the branch.
He can test the branch in his local or remote test server.
We provide remote test server to test specified branch.
The server ip is 54.85.249.210 and you need to register your ssh key to access this server via SSH.
ITS will help ssh key registeration.
After login this server, please run following terminal commands to switch the branch you wanna test.

    cd /home/ubuntu/tmtext/

    git fetch --all

    git checkout branch_name

    git pull origin branch_name

    sudo reboot

After reboot this test server(please wait about 3 mins to be ready all services running after reboot), you can check the scraper response in your web browser like following:

http://54.85.249.210/get_data?url=http://www.walmart.com/ip/35902520

If you find any issues or missing requirements, you need to update the ticket with the detail comments to fix issues for developers.
If you are satisified at the works, you can merge the branch into master.

3) After PM merges the branch into master, the QA(Adriana) checks the scraper response in the master branch test server like following:

http://52.1.156.214/get_data?url=http://www.walmart.com/ip/21968667

This test server always keeps the latest master branch by Jenkins.
If you find any issues or missing requirements, you need to update the ticket with the detail comments to fix issues for developers.
If you are satisified at the works, you need to update the ticket to deploy the scraper to the production.
Also please purge AWS Queue Messages and kill instances before run the batch.
ITS will assist this.

4) After QA's approve regarding production deployment, PM deploys the scraper into production by merging master into production.
Here are detail steps to deploy from master to production.

access to the remote server **52.0.145.221** via ssh

go to /home/ubuntu/Git Workspace/master and run following commands

    git pull origin master

go to /home/ubuntu/Git Workspace/production and run following commands

    git pull origin production

    rm -rf special_crawler/

    rm -rf spiders_shared_code/

    cp -Ri ../master/special_crawler/ special_crawler

    cp -Ri ../master/spiders_shared_code/ spiders_shared_code

    git add .

    git commit -am "Your comment"

    git push origin-push production

The password is "Nimda1235"

Please don't work in other folders in this server.

That's all
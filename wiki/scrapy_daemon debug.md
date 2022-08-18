# Login to remote instance
ssh ubuntu@52.90.73.172   (replace with actual IP)

su spiders
pwd spiders

CHECK for spiders:
 ps -AF | grep spiders

# Go into virtualenv:

source /home/spiders/virtual_environment/bin/activate && cd /home/spiders/repo/tmtext/product-ranking/product_ranking

# RUN scrapy_daemon:

cd ~/repo/tmtext/deploy/sqs_ranking_spiders/
python scrapy_daemon.py

scrapy_daemon logs are here -- but if you run the above from the command line you can see the output at the console. Check if it's running first. If so, "kill" it so you can run it from command line instead.

/tmp/remote_instance_starter2.log

# If you want to run a test crawl to test a spider:

/home/spiders/virtual_environment/bin/python /home/spiders/virtual_environment/bin/scrapy crawl amazon_products -a product_url=http://www.amazon.com/Levis-Womens-Perfectly-Slimming-Bootcut/dp/B004WI25TK -a make_screenshot_for_url=False -a ignore_variant_data=False -a scrape_questions=True -a use_data_from_redirect_url=0


# SCCluster1-killer
This instance runs a script that checks all the Sc crawler instances and sees if they are hung. If so it kills them after 32 minutes. So if you are trying to debug on production instance... you may want to terminate the script or "stop" the instance temporarily.


# Add Andrii to an instance:
echo 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCtX9S7mJ2S25jOBJSKHUBrTF5P4+oxWdVetWjH+8MmMau+XtyGV5rjAKAigg7FleRsgUr6xQfwnCDab/wbZIf8TV64LHa25DaCnt8AagBW7+8WtRX3+yB4/5jcHBS7FnxXkgInHmU+28fQ5lw4Pn79+a/KX/FHPDzoVeiItg0TJFJCw++L5hpV1R9yU4QAes4iD+Co4ex7qWqvWMHVCHuMD3RjRRPzLEzi+yh0c2g4yXg52aq1sHaZxm0hQw76VebxpMZRcN9XlxxpS6iCAGNCeZHrK0z62PpOqKjzw9zZMk/XjBbm85dg9hUfaB/ogJine2jcfaInbjB4dXCJIpfT konokrad@kono-V560' >> /home/ubuntu/.ssh/authorized_keys
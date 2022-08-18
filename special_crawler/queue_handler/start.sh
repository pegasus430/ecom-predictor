#!/bin/bash

source /home/ubuntu/tmtextenv/bin/activate

export AWS_TAG_NAME="Environment"
export AWS_INSTANCE_ID="`curl -s http://169.254.169.254/latest/meta-data/instance-id`"
export AWS_REGION="`curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e 's:\([0-9][0-9]*\)[a-z]*\$:\\1:'`"
export AWS_TAG_VALUE="`aws ec2 describe-tags --filters "Name=resource-id,Values=$AWS_INSTANCE_ID" "Name=key,Values=$AWS_TAG_NAME" --region $AWS_REGION --output=text | cut -f5`"

#echo "$AWS_TAG_VALUE"
sudo -u ubuntu /home/ubuntu/tmtextenv/bin/python /home/ubuntu/tmtext/special_crawler/queue_handler/get_scrape_queue.py "$AWS_TAG_VALUE" &> queue.log

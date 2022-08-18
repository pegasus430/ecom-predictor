1) Check SQS queues, see if messages are being processed at all

https://console.aws.amazon.com/ec2/autoscaling/home?region=us-east-1#AutoScalingGroups:view=details



2) Check the corresponding AutoScale cluster to make sure there are instances running

https://console.aws.amazon.com/sqs/home?region=us-east-1#queue-browser:prefix=



3) Login to Crawlera, see if there is an obvious site issue

https://app.scrapinghub.com/o/38810/crawlera/content?status=any&website=any
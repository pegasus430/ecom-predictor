Before run - don't forget to run celery worker
run example (from "python/content_parser" directory):
nohup celery -A tasks.celery worker --concurrency=1 -B >>celery.log 2>&1 &

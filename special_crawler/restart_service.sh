# use this script to restart the service automatically and log its output/errors
# to install as a cronjob to restart it daily:
# 	- run "sudo crontab -u root -e"
#  	- add this:
#   	# restart walmart_media_app service once a day
#		00 00 * * * /bin/bash /home/ubuntu/tmtext/special_crawler/restart_service.sh 2>> /tmp/restart_specialcrawler_errors.txt

dir="/home/ubuntu/tmtext/special_crawler"
mkdir -p "$dir"/logs
/usr/bin/pkill -f walmart_data_service;
/usr/bin/screen -dm /bin/bash "$dir"/start_service.sh 2>>"$dir"/logs/startservice_log.txt

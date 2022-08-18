dir="/home/ubuntu/tmtext/special_crawler"
mkdir -p "$dir"/logs
time=`date +"%F"`
python "$dir"/walmart_data_service.py 2>>"$dir"/logs/log_"$time".txt

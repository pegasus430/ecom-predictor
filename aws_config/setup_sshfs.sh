#!/bin/bash

# ip of machine to mount in shared folder
# usually private ip of node1
#IP="10.170.60.95"

# usually for node 2..10
./get_private_ips.sh 1
for node in "$@"
do
	IP=`cat hosts | python -c "import sys; print sys.stdin.read().split()[1]"`
	#vagrant ssh node$node -c 'rm /home/ubuntu/shared_sshfs/*; /usr/bin/sshfs -d -o StrictHostKeyChecking=no ubuntu@10.91.176.34:/home/ubuntu/shared_sshfs /home/ubuntu/shared_sshfs 2> sshfslog; sleep 5; ls /home/ubuntu/shared_sshfs';
	#vagrant ssh node$node -c 'screen -dm /usr/bin/nohup /usr/bin/sshfs -d -o ssh_command="ssh -i /home/ubuntu/.ssh/id_rsa" -o StrictHostKeyChecking=no ubuntu@10.91.176.34:/home/ubuntu/shared_sshfs /home/ubuntu/shared_sshfs &';
	vagrant ssh node$node -c "screen -S sshfs -dm /bin/bash /home/ubuntu/sshfs_script.sh $IP; sleep 5"
done

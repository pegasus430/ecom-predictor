#!/bin/bash

# check if sshfs is running (directory is already mounted)
CHECK=`ps xau | grep sshfs | grep -v grep | wc -l`
if [ $CHECK -gt 0 ]; then
	sudo umount /home/ubuntu/shared_sshfs;
fi
rm /home/ubuntu/shared_sshfs/*;
/usr/bin/sshfs -d -o ssh_command="ssh -i /home/ubuntu/.ssh/id_rsa" -o StrictHostKeyChecking=no ubuntu@"$1":/home/ubuntu/shared_sshfs /home/ubuntu/shared_sshfs
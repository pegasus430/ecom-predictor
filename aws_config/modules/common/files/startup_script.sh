#!/bin/bash

/etc/init.d/networking restart

cd /home/ubuntu/tmtext; 
/usr/bin/git pull origin master
chown -R ubuntu:ubuntu /home/ubuntu/tmtext


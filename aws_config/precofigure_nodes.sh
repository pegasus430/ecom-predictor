#!/bin/bash

# set hostname and install puppet on every node with vagrant ssh -c
for node in "$@"
	do 
	vagrant ssh "node$node" -c \
		"echo 'node$node' | sudo tee /etc/hostname; \
		sudo hostname node$node; \
		echo '127.0.1.1 node$node' | sudo tee -a /etc/hosts; \
		sudo apt-get update; \
		sudo apt-get install -y puppet";
	done;
	vagrant reload "node$node"
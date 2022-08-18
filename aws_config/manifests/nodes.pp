node default {


	service { "networking":
    	provider => 'base',
	    path => '/etc/init.d/networking',
	    start => '/etc/init.d/networking start',
    	ensure => 'running',
  	}

	exec { 'apt-update-1':
		command => '/usr/bin/apt-get update',
		require => Service['networking'],
	}

	# packages
	package { 'git':
		ensure => present,
		require => Exec['apt-update-1'],
	}
	
	package { 'python-pip':
		ensure => present,
		require => Exec['apt-update-1'],
	}

	package { 'python-dev':
		ensure => present,
		require => Exec['apt-update-1'],
	}

  package { 'python-opencv':
    ensure => present,
    require => Exec['apt-update-1'],
  }

	package {'libxslt1-dev':
   		ensure => present,
 		require => Exec['apt-update-1']
	}

	package {'sshfs':
   		ensure => present,
 		require => Exec['apt-update-1']
	}


	# python packages

	package { 'scrapy':
    # ensure => present,
		ensure => '1.0',
		provider => 'pip',
		require => [Package['python-pip'], Package['python-dev'], Package['libxslt1-dev']],
	}

	package { 'nltk':
		ensure => present,
		provider => 'pip',
		require => Package['python-pip'],
	}

	package { 'selenium':
		ensure => present,
		provider => 'pip',
		require => Package['python-pip'],
	}

  package { 'numpy':
    ensure => present,
    provider => 'pip',
    require => Package['python-pip'],
  }

	# SSH

	# # ssh keys
	# file { "/home/ubuntu/.ssh":
 #    	ensure => "directory",
 #    	owner  => "ubuntu",
 #    	group  => "ubuntu",
 #    	mode   => 600,
 #  	}

	# file { "/home/ubuntu/.ssh/id_rsa":
	# 	source => "puppet:///modules/common/id_rsa",
	# 	mode => 600,
	# 	owner => ubuntu,
	# 	group => ubuntu,
	# }

	# file { "/home/ubuntu/.ssh/id_rsa.pub":
	# 	source => "puppet:///modules/common/id_rsa.pub",
	# 	mode => 644,
	# 	owner => ubuntu,
	# 	group => ubuntu,
	# }

 #  ssh_authorized_key { "ssh_key":
 #    ensure => "present",
 #    key    => "AAAAB3NzaC1yc2EAAAADAQABAAABAQCe+SG4qezR2z8Ma1JR4Uux9XtuwyFlQT8tk3pMBr0WIBIXaOICIa6YM9xeBHsUb24IVk4KQs8pmY42q1P8MjqIIXA62q4G2nqRn97I3/W2KLH4z4QRNnG8UPkOvGcW0XaKjzSKdEepWBDTIxKeVdRbhlr2ZSp3/FGlbQ2KhqffIg65X3fnvPTorCh4X85iqvfhibddiRC+DmKvVKvrgrw5q/YysB4e0Ho5ql6UiKlCtU88o1yyrXeiPAlYhI4HFfrlaISEg0WUPxotBmpLZXOPb9UvG5wQ4i3FGj8fW1hGhn5E2zxe1o+GyPssTR25fnyATj17Nnm+z8r/C3SE7xyD",
 #    type   => "ssh-rsa",
 #    user   => "ubuntu",
 #  }

  # create folder to share between them
    file { "/home/ubuntu/shared_sshfs":
      ensure => "directory",
      owner  => "ubuntu",
      group  => "ubuntu",
      mode => 644
      #creates => "/home/ubuntu/shared_sshfs"
    }

  exec { "create-shared-sshfs":
    # return successful whatever mkdir returns (it will return 1 if shared_sshfs mounted)
    command => "/bin/mkdir shared_sshfs || true",
    cwd => "/home/ubuntu",
    user => "ubuntu",
    creates => "/home/ubuntu/shared_sshfs"
  }


	# make sure root has access to repo (to pull at startup)
	file { "/root/.ssh/config":
	    source => "puppet:///modules/common/ssh_config",
    	owner => root,
    	group => root,
    	mode => 644
  	}

  	# add config file to ubuntu user as well to skip identifying bitbucket on clone
	file { "/home/ubuntu/.ssh/config":
	    source => "puppet:///modules/common/ssh_config",
    	owner => ubuntu,
    	group => ubuntu,
    	mode => 644
  	}


  	# git repo

	# # clone repo if it doesn't exist
	# exec {"clone-tmtext":
	# 	creates => "/home/ubuntu/tmtext",
	# 	cwd => "/home/ubuntu",
	# 	user => "ubuntu",
	# 	command => "/usr/bin/git clone -q git@bitbucket.org:dfeinleib/tmtext.git",
	# 	require => Package['git'],
	# }

 #  	# startup script - pulling from repo
 #  	file { "/home/ubuntu/startup_script.sh":
 #    	source => "puppet:///modules/common/startup_script.sh",
 #    	owner => root,
 #    	group => root,
 #    	mode => 777
 #  	}

    # add script to open sshfs
    file { "/home/ubuntu/sshfs_script.sh":
      source => "puppet:///modules/common/sshfs_script.sh",
      owner => ubuntu,
      group => ubuntu,
      mode => 777
    }

  	# file { "/etc/rc.local":
   #  	source => "puppet:///modules/common/rc.local",
   #  	owner => root,
   #  	group => root,
   #  	mode => 755
  	# }
}
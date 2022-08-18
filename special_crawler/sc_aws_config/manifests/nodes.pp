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
		ensure => present,
		provider => 'pip',
		require => [Package['python-pip'], Package['python-dev'], Package['libxslt1-dev']],
	}

	package { 'selenium':
		ensure => present,
		provider => 'pip',
		require => Package['python-pip'],
	}

  package { 'flask':
    ensure => present,
    provider => 'pip',
    require => Package['python-pip'],
  }

 #  # git repo

	# # clone repo if it doesn't exist
	# exec {"clone-tmtext":
	# 	creates => "/home/ubuntu/tmtext",
	# 	cwd => "/home/ubuntu",
	# 	user => "ubuntu",
	# 	command => "/usr/bin/git clone -q git@bitbucket.org:dfeinleib/tmtext.git",
	# 	require => Package['git'],
    # }

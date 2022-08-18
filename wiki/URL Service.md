## Overview ##

This is a simple service that provides a queue of URLs and allows to store the results of processing those URLs.

This service depends on the following modules:

- pyramid

Tests are included and require a additional modules to work:

- requests


## Environment Setup ##

To use it in a test environment, using `virtualenv` do the following:

    # cd url_service
    # virtualenv --clear .
    # source bin/activate
    # pip install pyramid
    # pip install requests
    # python url_service.py

And in another terminal:

    # cd url_service
    # source bin/activate
    # python -m unittest tests_url_service.py

If that works, the environment is OK and the service is working properly.


## Step by step instructions ##

The detailed instructions to setup the environment to test the server are:

1. [Setup VirtualEnv](VirtualEnv Setup)
1. [Setup Git](Git Setup)
1. Clone the git repository: `git clone git@bitbucket.org:dfeinleib/tmtext.git`
1. Change dir to the project's directory: `cd tmtext/url_service`
1. Create a virtual environment: `virtualenv --no-site-packages .`
1. Activate the virtual environment: `source bin/activate`
1. Install dependencies: `pip install pyramid requests`
1. Start the server: `python url_service.py`

On another terminal:

1. Activate the virtual environment: `source bin/activate`
1. Run tests: `python -m unittest test_url_service`

If the output is as follows, the environment was setup correctly:

    .........
    ----------------------------------------------------------------------
    Ran 9 tests in 0.072s
    
    OK


## Things to improve ##

The drawbacks of the code are:

- Uses SQLite directly (no abstraction layer like SqlAlchemy).
- Writes to the location of url_service.py.
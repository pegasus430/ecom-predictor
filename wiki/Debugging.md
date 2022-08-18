DEBUGGING Notes:

1) Add more logging INSIDE each function. Quick and easy to do, provides a lot of info about where a process may be failing.

2) Run each component piece from the command line - this will eliminate pieces that are not causing the issue:
* run the scraper 
* run scrapy_daemon

3) Find faster ways to debug - don’t wait for instances to spin up.
Example: When possible, logging to the console (for debugging purposes) is faster and provides real-time info. For unfamiliar code, e.g. scrapy_daemon, logging is the first place to start. Don’t wait for someone else to dig in — dive into the code and see if you can pinpoint the issue.

4) When something works in test but not prod, if it cannot be fixed after 1 -2 tries via fix in test, it has to be debugged one step at a time in prod. Not on a customer instance, but in prod.

5) Clean up old dependencies, missing files, etc. They are distracting while debugging

scrapy_daemon notes: https://bitbucket.org/dfeinleib/tmtext/wiki/scrapy_daemon%20debug
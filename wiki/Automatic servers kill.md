There is a script executed every 17 minutes.

It is located at product-ranking/sqs_tests_gui/kill_servers/management/commands and named check_branch_and_kill.py (use as the appropriate Django command).

It's currently deployed at sqs-tools server.

It checks `sc_production` branch for changes and - if there have been some changes since last check - it then:

1) kills all production SC servers in all SC autoscale groups (by scaling the groups down using `max_size = 0` code);

2) waits till there are no servers running (i.e. current size == 0)

3) restores all the groups max sizes back to previous `max_size` values (the values that were before sizes set to 0).

You can see the restart log here: http://sqs-tools.contentanalyticsinc.com/kill-restore-servers/

Stats for currently running servers and SQS messages is here: http://sqs-tools.contentanalyticsinc.com/sqs-stats/


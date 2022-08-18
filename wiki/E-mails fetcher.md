Source location: `repo:tmtext/email_fetcher`

Script at `import.contentanalyticsinc.com` for searching emails by subject, reading zip archives and uploading extracted files to FTP server. Script is running via cron job every day.

Script location: `/usr/local/scripts/crons/fetcher.py`

Config location: `/usr/local/scripts/crons/config.json`

Log location: `/var/log/fetcher.log`

Script could fetch messages from several email boxes one by one. You must create fetcher record for each:

* name - fetcher name
* email - email box settings
* * server - IMAP server address
* * box - email box name
* * password - email password 
* * subjects - you can specify several subjects for fetching. Placeholders for format of output file name:
* * * subject - current subject
* * * name - attachment file name
* * * date - email date
* * * ext - attachment extension
* ftp - FTP settings
* * server - server address
* * user - user name
* * password - FTP password
* * dir - directory on FTP server for uploads

Example config:

```
#!js

[
  {
    "name": "traffic",
    "email": {
      "server": "imap.gmail.com",
      "box": "import_sams@contentanalyticsinc.com",
      "password": "",
      "subjects": {
        "mWeb Natural Search Entry Page Metrics": "{subject}_{date}{ext}",
        "Ad Hoc Analysis - Natural Search Entry Pages - Mobile": "{subject}_{date}{ext}",
        "Desktop Natural Search Entry Page Metrics": "{subject}_{date}{ext}"
      }
    },
    "ftp": {
      "server": "54.175.228.114",
      "user": "samsclubemail",
      "password": "",
      "dir": "upload"
    }
  },
  {...},
  {...}
]

```

Create new config file and cron job if you need to fetch other email box in other time. Script has `--config` and `--log` arguments.
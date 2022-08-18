If you're looking for a password to access some web site(s) related to SC, try this password:



```
#!
gLfb-N4gd<
```



(The username is normally "admin", if it asks you to enter that)

**Be careful if you want to change it**! It is currently used in SQS Cache! Search the _whole_ codebase for the old password and update it if needed.

Currently, this password is used on the following websites:

* sqs-tools (Django "admin" user password)

* sqs-metrics (Nginx auth file)
  
* sc-tests (Nginx auth file)

All these domains are 3-rd level. Add ".contentanalyticsinc.com" to each of them to open the actual website.

To change the password on the websites, you need to update the Nginx auth file on each site OR the Django password for "admin" user. Then restart Nginx, if you have changed its auth file. Auth file update can be achieved by several ways, see https://www.digitalocean.com/community/tutorials/how-to-set-up-http-authentication-with-nginx-on-ubuntu-12-10 for one. Django's password can be changed at http://sqs-tools.contentanalyticsinc.com/admin/password_change/

**Attention**! Save the old password somewhere (like your local text file) before changing it. You will need it to update Django's password.
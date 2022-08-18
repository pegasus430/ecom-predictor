### Purpose ###

Rotating proxies and providing single entry point for them.

### HAProxy ###

Internal server **proxy_out.contentanalyticsinc.com** (external IP 34.205.229.206)

Stats: http://admin:password@proxy_out.contentanalyticsinc.com

Current proxies:

* tors `proxy_out.contentanalyticsinc.com:22099`
* rotatingproxies.com `proxy_out.contentanalyticsinc.com:48359`
* shader.io `proxy_out.contentanalyticsinc.com:60000`

**Install**

```
#!bash

sudo add-apt-repository ppa:vbernat/haproxy-1.7
sudo apt-get update
sudo apt-get install haproxy
sudo service haproxy restart
```

**Fixing logging**

Add in `/etc/logrotate.d/haproxy`: `su root syslog`
```
#!bash

sudo service rsyslog restart
sudo logrotate /etc/logrotate.d/haproxy
sudo service haproxy restart
```

**Adding new set of proxies**

Config: `/etc/haproxy/haproxy.cfg`


```
#!text

frontend NAME_OF_FRONTEND
    bind :FRONT_END_PORT
    default_backend NAME_OF_BACKEND

backend NAME_OF_BACKEND
    balance hdr(x-session)

    server PROXY_NAME PROXY_IP:PROXY_PORT check
    ...
```

If proxy server requires authorisation add `reqadd Proxy-Authorization:\ Basic\ BASE64_ENCODED_USER:PASSWORD` in backend section

If list of proxies are big and get error `[haproxy.main()] Cannot fork` during restart, remove health `check` for them

**Using sessions**

To stick spider to one proxy address use HTTP header `x-session`. If Spider with that session was blocked just change value of header on other random string.
If header doesn't exist HAPRoxy [rotates proxies](http://cbonte.github.io/haproxy-dconv/1.7/configuration.html#balance)

*Note: Current load balancing algorithm doesn't allow to remove that header from outgoing request*

**Testing**

Rotating: `curl -x http://proxy_out.contentanalyticsinc.com:22099 http://checkip.amazonaws.com/`

Session: `curl -x http://proxy_out.contentanalyticsinc.com:22099 -H 'x-session: sess' http://checkip.amazonaws.com/`
[TOC]

# What it is

It's a bunch of proxy chains, running on a single server. Every chain consists of the following nodes:

1) TOR (apt-get install tor) - SOCKS proxy

2) Polipo (apt-get install polipo) - HTTP proxy that just redirects the traffic to the TOR node from #1

Why Polipo? Because Scrapy does not support SOCKS proxies.

There are 300 chains running on the server.

# Why

Because some websites block our IPs. We have to recognize captchas (and it may fail), or sometimes we can't even do anything with it (we get banned completely).

# Spiders support

Currently, the following spiders run through the TOR proxies:

1. cvs_shelf_urls_products
1. zulily_products
1. levi_products
1. walmart_grocery_products
1. dockers_products
1. macys_products
1. shopritedelivers_products


# Proxy server

Hostname: tprox.contentanalyticsinc.com

IP: dynamic (pls rely on the hostname rather than on the IP)

## Proxy ports

SOCKS: 21100-21400

HTTP: 22100-22400

Use any of them. Their IPs are rotated from time to time. All of the IPs in this range (300 IPs) should be mostly different (i.e. there shouldn't be many duplicated IPs).

## Firewall and accessibility

The ports are closed from outside of our private network, for security reasons. The proxies will NOT be available from the "Internet".

## Setting up the server

To set up a TOR proxy server, do this.

* upload the code from '/tor_proxies' dir to the chosen server

* install tor and polipo (apt-get install tor polipo)

* you may not be able to run the code from a user with low permissions - try ubuntu and root

* cd to the dir with the run_tor.py script; run it: python run_tor.py

* wait for about 5 mins and check the proxies

* sometimes polipo processes fail, so it's better to have something like this line in your crontab:

```
*/17 *  *   *   *    cd /home/ubuntu/tor_proxy; python run_tor.py > /tmp/run_tor.log 2>&1
```

(check that it works killing all TOR and polipo processes by "killall" and checking that they are running again after ~20 mins)

# Usage example

(from one of our EC2 instances)

```
>>> import requests
>>> print requests.get('http://www.telize.com/geoip', proxies={'http': 'http://tprox.contentanalyticsinc.com:22100'}).text

{"longitude":9,"latitude":51,"asn":"AS24940","offset":"2","ip":"176.9.99.134","area_code":"0","continent_code":"EU","dma_code":"0","timezone":"Europe\/Berlin","country_code":"DE","isp":"Hetzner Online AG","country":"Germany","country_code3":"DEU"}
```
"""
This tool downloads all sitemap files from walmart.com and create a csv file
with all product urls
"""
import os
from time import time, sleep
import requests
import urllib2
import gzip
import re

def get_links_sitemap(url="http://www.walmart.com/sitemap_ip.xml",folder="urlsgz"):
    #Get sitemap as gz files from walmart.com
    start_time = time()
    if not os.path.exists(folder):
        os.makedirs(folder)
    res = urllib2.urlopen(url).readlines()
    lnks = []
    for d in res:
      data = re.findall('<loc>(http:\/\/.+)<\/loc>',d)
      for i in data:
        lnks.append(i)
        download_file(i,folder)
        print i,"Time :",time() - start_time, "seconds"
    return lnks


def download_file(url,folder):
    #Download file from walmart.com
    t = requests.get(url,stream=True)
    local_filename = url.split("/")[-1]
    f = open(folder+"/"+local_filename,"wb")
    f.write(t.raw.read())
    f.close()


def create_full_list(folder = "urlsgz"):
    #Collect all product urls in one csv file
    f = open("full_urls.csv","wb")
    start_time = time()
    print "Create full_urls.csv"
    for filename in os.listdir(folder):
        print filename
        handle = gzip.open( folder+"/"+filename)
        for line in handle:
          data = re.findall('<loc>(http:\/\/.+)<\/loc>',line)
          for link in data:
            f.write(link+"\n")
        print "Time :",time() - start_time, "seconds"
    f.close()


if __name__ == '__main__':
    #Save sitemap files and create csv file with all walmart product urls
    url="http://www.walmart.com/sitemap_ip.xml"
    folder="urlsgz"
    get_links_sitemap(url,folder)
    sleep(1)
    create_full_list(folder)
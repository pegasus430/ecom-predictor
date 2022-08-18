#!/usr/bin/python
#  -*- coding: utf-8 -*-

# Author: Marek Glica
# This is sitemap extractor to grab product page URLs from xml page.
# for ex) http://www.babysecurity.co.uk/sitemap.xml
# And this prints the output and exports the output in txt file.
# Arguments are as follows.
# sitemap URL, output txt filename, changefreq, priority
# for ex: python sitemap_extractor.py "http://www.babysecurity.co.uk/sitemap.xml" babysecurity_sitemap.txt daily 1.0
# In the sitemap xml, there are <changefreq>daily</changefreq> and <priority>1.0</priority>.

import sys
import urllib
from xml.dom import minidom


# def sitemap_extractor(url, outputfile, changefreq, priority):
#     """
#     This grabs all project URLs of which priority is equal or greater than <priority>, changefreq is <changefreq>.
#     And then prints result in screen and <outputfile>.
#     :param url: URL string to curl
#     :param outputfile: text filename to store result
#     :param changefreq: daily or other
#     :param priority: float
#     """
#     print "grabbing product URLs..."
#     contents = urllib.urlopen(url).read()
#     xmldoc = minidom.parseString(contents)
#     itemlist = xmldoc.getElementsByTagName('url')
#     urls = []
#     for url_entry in itemlist:
#         str_changefreq = url_entry.getElementsByTagName("changefreq")[0].firstChild.nodeValue
#         f_priority = float(url_entry.getElementsByTagName("priority")[0].firstChild.nodeValue)
#         if str_changefreq == changefreq and f_priority >= priority:
#             str_loc = url_entry.getElementsByTagName("loc")[0].firstChild.nodeValue
#             urls.append(str_loc)
#     urls_txt = "\n".join(urls)
#     print "Stored %s product URLs in %s file" % (len(urls), outputfile)
#     # print urls_txt
#     text_file = open(outputfile, "w")
#     text_file.write(urls_txt)
#     text_file.close()
#     return


def sitemap_extractor(url, outputfile, changefreq=None, priority=None):
    """
    This grabs all project URLs of which priority is equal or greater than <priority>, changefreq is <changefreq>.
    And then prints result in screen and <outputfile>.
    :param url: URL string to curl
    :param outputfile: text filename to store result
    :param changefreq: daily or other
    :param priority: float
    """
    print "grabbing product URLs..."
    contents = urllib.urlopen(url).read()
    xmldoc = minidom.parseString(contents)
    itemlist = xmldoc.getElementsByTagName('url')
    urls = []
    for url_entry in itemlist:
        if changefreq is not None and priority is not None:
            str_changefreq = url_entry.getElementsByTagName("changefreq")[0].firstChild.nodeValue
            f_priority = float(url_entry.getElementsByTagName("priority")[0].firstChild.nodeValue)
            if str_changefreq == changefreq and f_priority >= priority:
                str_loc = url_entry.getElementsByTagName("loc")[0].firstChild.nodeValue
                urls.append(str_loc)
        else:
            str_loc = url_entry.getElementsByTagName("loc")[0].firstChild.nodeValue
            urls.append(str_loc)

    urls_txt = "\n".join(urls)
    print "Stored %s product URLs in %s file" % (len(urls), outputfile)
    # print urls_txt
    text_file = open(outputfile, "w")
    text_file.write(urls_txt)
    text_file.close()
    return


if __name__ == "__main__":
    if len(sys.argv) > 2:
        url = sys.argv[1] # ' http://www.babysecurity.co.uk/sitemap.xml'
        outputfile = sys.argv[2]
        try:
            changefreq = sys.argv[3]
            priority = float(sys.argv[4])
        except IndexError:
            changefreq = None
            priority = None
        sitemap_extractor(url, outputfile, changefreq, priority)
    else:
        print "######################################################################################################"
        print "This is a sitemap extractor to grab product page URLs from xml page.(Author: Marek Glica)"
        print "Please input correct arguments.\nfor ex: python sitemap_extractor.py \"http://www.babysecurity.co.uk/sitemap.xml\" babysecurity_sitemap.txt daily 1.0"
        print "\t\tThis grabs all product URLs of which <priority> is equal or greater than 1.0 and <changefreq> is 'daily'."
        print "\t\tAnd this exports product URLs in babysecurity_sitemap.txt file."
        print "######################################################################################################"

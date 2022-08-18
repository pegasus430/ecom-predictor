#!/usr/bin/python

import codecs
import json
from pprint import pprint



# returns dictionary with number of levels and number of categories on each level for a site
def number_of_levels(site):
    # filename is of form "Site/site_categories.jl"
    filename = site[0].upper() + site[1:] + "/" + site + "_categories.jl"
    # separate handling for BJs
    if site.strip() == "bjs":
        filename = "BJs/bjs_categories.jl"
    f = codecs.open(filename, "r", "utf-8")

    levels = {}
    for line in f:
        item = json.loads(line.strip())
        level = item['level']
        if level not in levels:
            levels[level] = 1
        else:
            levels[level] += 1
    levels["nrlevels"] = len(levels.keys())
    levels["site"] = site
    return levels

# prints table with number of levels and of categories on each level for a list of sites
def levels_table(sites):
    levels = {}

    # print it
    #TODO: levels up to 2? how do you handle it?
    print "%20s%20s%20s%20s%20s" % ("Site", "Nr levels", "Departments", "Categories", "Subcategories")
    print "-------------------------------------------------------------------------------------------------------"
    for site in sites:
        levels = number_of_levels(site)
        print "%20s%20d%20d%20d%20d" % (site, levels['nrlevels'], levels.get(1,0), levels.get(0,0), levels.get(-1,0))

sites = ["amazon", "bestbuy", "bjs", "bloomingdales", "overstock", "walmart", "wayfair"]
levels_table(sites)
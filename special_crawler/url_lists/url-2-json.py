# !/usr/bin/python
# -*- coding: utf-8 -*-

"""
Converts a csv of urls into a directory of scraped, utf-8 encoded, .json files

$ python cururls.py [urlcsvfile] [resultsdir]

"""
import csv , os ,  subprocess , sys , re

urlcsvfile = open(sys.argv[1], 'r')
resultsdir = sys.argv[2]
mkresultsdir = os.system("mkdir %s" % resultsdir)

filecount = 1

for url in urlcsvfile:
        m = re.match("(#.*)", url)
        if m:
            print url
        else:
            print url
	    curling = subprocess.Popen(["curl" , "localhost/get_data?url={url}".format( url = url) ] , stdout=subprocess.PIPE , stderr=subprocess.PIPE)
	    out , err = curling.communicate()
	    print err
	
	    outfile = open(os.path.join(resultsdir + "/" , "%s.json" % filecount), "w")
	    decodedLine = out.decode("unicode escape")
	    outfile.write(url)
	    outfile.write(decodedLine.encode("utf-8"))
	    outfile.close()
	    filecount = filecount + 1
	
	    #curling2 = subprocess.check_output(["curl" , "%s" % url])

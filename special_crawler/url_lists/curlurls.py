"""
$ python cururls.py [urlcsvfile] [resultsdir]
"""
import csv , os ,  subprocess , sys , re

urlcsvfile = open(sys.argv[1], 'r')
resultsdir = sys.argv[2]
mkresultsdir = os.system("mkdir %s" % resultsdir)

filecount = 1
comment = ""

for row in csv.reader(urlcsvfile):
        url = row[0]
        m = re.match("(#.*)", url)
        if m:
            print url
            comment = url
        else:
            print url
            curling = subprocess.Popen(["curl" , "localhost/get_data?url={url}".format( url = url) ] , stdout=subprocess.PIPE , stderr=subprocess.PIPE)
            out , err = curling.communicate()
            print err
            outfile = open(os.path.join(resultsdir + "/" , "%s.txt" % filecount), "w")
            outfile.write(url)
            outfile.write("\n")
            outfile.write(comment)
            outfile.write("\n")
            outfile.write(out)
            outfile.close()
            filecount = filecount + 1

       #curling2 = subprocess.check_output(["curl" , "%s" % url])

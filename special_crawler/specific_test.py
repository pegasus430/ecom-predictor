"""
UnitTesting Service

* Make sure a crawler_service is running in order to test
* Make sure specific_test.py is run from the directory with the json files

This accomplishes the following:
1. look through current directory
2. find all "extract_<SUPPORTED_SITE>_test.json
    these json files are lists of dicts,
    the dicts are expected outputs from a site
3. Look into the dict to find what url it's from
4. Run the scraper (running on localhost) on the urls
5. compare the expected vs. actual results
    strings are compared using a Levenshtein distance
    formula, and a threshold is set so that very 
    similar strings map as the same
6. display differences.

"""

import requests
from flask import Flask, jsonify, abort, request
import os
import json
import unittest

#This class gets built out dynamically
class SpecTest(unittest.TestCase):
    pass

# levenshtein distance formula - adapted from http://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Levenshtein_distance#Python
# this is able to tell how similar two strings are
# note it doesn't compare the whole string if its long, just the ends
def lev(self, seq1, seq2):
    seq1 = seq1.strip()
    seq2 = seq2.strip()
    ends = 30 #how much of the ends to compare
    if(len(seq1) > (2*ends)):
        seq1 = seq1[0:ends] + seq1[len(seq1)-ends:]
    if(len(seq2) > (2*ends)):
        seq2 = seq2[0:ends] + seq2[len(seq2)-ends:]
    oneago = None
    thisrow = range(1, len(seq2) + 1) + [0]
    for x in xrange(len(seq1)):
        twoago, oneago, thisrow = oneago, thisrow, [0] * len(seq2) + [x + 1]
        for y in xrange(len(seq2)):
            delcost = oneago[y] + 1
            addcost = thisrow[y - 1] + 1
            subcost = oneago[y - 1] + (seq1[x] != seq2[y])
            thisrow[y] = min(delcost, addcost, subcost)
    dist = thisrow[len(seq2) - 1]
    percent = dist/(1.*len(seq1)+len(seq2))*2
    return percent


def create_test (expected, actual):
    def do_test_expected(self):
        if(isinstance(expected, int) 
                or isinstance(expected, bool) 
                or isinstance(expected, float)):
            self.assertEqual(expected, actual)

        elif(isinstance(expected, str)):
            self.assertTrue(lev(pair[0]), pair[1])

        elif(isinstance(expected, list)):
            self.assertEqual(expected, actual)

        else:
            pass
    return do_test_expected

def load_test(expected, actual, name):
    test_method = create_test(expected, actual)
    test_method.__name__ = 'test_%s' % str(name)
    setattr (SpecTest, test_method.__name__, test_method)

SUPPORTED_SITES = [
                   "amazon" ,
                   "argos",
                   "bestbuy" ,
                   "homedepot" ,
                   "kmart" ,
                   "ozon" ,
                   "pgestore" ,
                   "statelinetack" ,
                   "target" ,
                   "tesco" ,
                   "vitadepot",
                   "walmart" ,
                   "wayfair" ,
                   ]

DONT_CHECK = [
                "date",
                "loaded_in_seconds"
                ]

# traverse down 2 proposedly similar dictionaries and test if they're identical
# expected dict, actual dict, and the current branch within the dictionary tree
def compare_dict(expected, actual, branch):
     # KEY DIFFERENCES
    expected_extra_keys = [x for x in expected.keys() if x not in actual.keys()]
    actual_extra_keys = [x for x in actual.keys() if x not in expected.keys()]

    load_test([], expected_extra_keys, "extra_keys_in_expected_not_in_actual")
    load_test([], actual_extra_keys, "extra_keys_in_actual_not_in_expected")


    # VALUE DIFFERENCES - The following codes was assisted by : http://stackoverflow.com/questions/2798956/python-unittest-generate-multiple-tests-programmatically                    
    union_keys = set(actual.keys()) & set(expected.keys())
    union_keys = union_keys.difference(DONT_CHECK)
    for key in union_keys:
        if(isinstance(expected[key], dict) and isinstance(actual[key], dict)):
            compare_dict(expected[key], actual[key], "%s > %s"%(branch, key))
        else:
            load_test(expected[key], actual[key], "%s > %s"%(branch, key))




def build_unit_test():
    for site in SUPPORTED_SITES:
        path = 'extract_%s_test.json'%site
        test_json = []
        if os.path.isfile(path):
            print "##################################################"
            print "################ SITE : ", site
            print "##################################################\n"

            try:
                f = open(path, 'r')
                s = f.read()
                if len(s) > 1:
                    test_json = json.loads(s)
                else:
                    raise Exception("json file not long enough")
            except Exception as e:
                print "Error loading json file: ", e
                f.close()
            else:
                f.close()

            for expected in test_json:
                url = expected['url']
                test_url = "http://localhost/get_data?site=%s&url=%s"%(site, url)
                actual = requests.get(test_url).text
                actual = json.loads(actual)
                compare_dict(expected, actual, url)

               


    
if __name__ == '__main__':
    build_unit_test()
    unittest.main()

    # app = Flask(__name__)
    # app.run('0.0.0.0', port=80, threaded=True)


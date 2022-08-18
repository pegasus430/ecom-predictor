#!/usr/bin/python
#
import unittest
import json
import re
import copy
import random
import psycopg2
import psycopg2.extras
import requests
import sys
import urllib
import signal
from datetime import date

SUPPORTED_SITES = ["walmart", "amazon", "amazon2", "jcpenney", "kohls", "macys", "target", "uniqlo", "levi", "dockers", "nike", "samsclub", "drugstore"]

def signal_handler(signum, frame):
    raise Exception("Timed out!")

DIFF_TEMPLATE = "<tr style='background-color: %s; color: white;'><td>%s</td><td>%s</td><td>%s</td></tr>\n"

def get_diff(test_json, sample_json, diff = None, path = ''):
    if not diff:
        diff = {
            'result' : '',
            'changes_in_structure' : 0,
            'changes_in_type' : 0,
            'changes_in_value' : 0
        }

    for k in sample_json:
        if k in ['date', 'loaded_in_seconds']:
            continue

        if path:
            new_path = path + '.' + k
        else:
            new_path = k

        if k in test_json:
            if isinstance(sample_json[k], dict):
                diff = get_diff(test_json[k], sample_json[k], diff, new_path)

            else:
                if type(test_json[k]) != type(sample_json[k]):
                    diff['result'] += DIFF_TEMPLATE % ('green', new_path, test_json[k], sample_json[k])
                    diff['changes_in_type'] += 1

                elif test_json[k] != sample_json[k]:
                    if isinstance(test_json[k], list):
                        if sorted(test_json[k]) != sorted(sample_json[k]):
                            current = []

                            for v in test_json[k]:
                                if not v in sample_json[k]:
                                    current.append(v)

                            sample = []

                            for v in sample_json[k]:
                                if not v in test_json[k]:
                                    sample.append(v)

                            diff['result'] += DIFF_TEMPLATE % ('blue', new_path, current, sample)
                            diff['changes_in_value'] += 1

                    else:
                        diff['result'] += DIFF_TEMPLATE % ('blue', new_path, test_json[k], sample_json[k])
                        diff['changes_in_value'] += 1

        else:
            diff['result'] += DIFF_TEMPLATE % ('black', new_path, None, sample_json[k])
            diff['changes_in_structure'] += 1

    for k in test_json:
        if path:
            new_path = path + '.' + k
        else:
            new_path = k

        if not k in sample_json:
            diff['result'] += DIFF_TEMPLATE % ('red', new_path, test_json[k], None)
            diff['changes_in_structure'] += 1

    return diff

class ServiceScraperTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(ServiceScraperTest, self).__init__(*args, **kwargs)

        is_valid_param = False

        if specified_website != "":
            for site in SUPPORTED_SITES:
                if site == specified_website:
                    is_valid_param = True
                    break

            if not is_valid_param:
                print "\nPlease input valid website name.\n-----------------------------------"

                for site in SUPPORTED_SITES:
                    sys.stdout.write(site + " ")

                print "\n"
                exit(1)

        try:
            self.con = None
#            self.con = psycopg2.connect(database='scraper_test', user='root', password='QdYoAAIMV46Kg2qB', host='127.0.0.1', port='5432')
            self.con = psycopg2.connect(database='scraper_test', user='root', password='QdYoAAIMV46Kg2qB', host='scraper-test.cmuq9py90auz.us-east-1.rds.amazonaws.com', port='5432')
            self.cur = self.con.cursor(cursor_factory=psycopg2.extras.DictCursor)
            self.urls_by_scraper = {}
        except Exception, e:
            print e

    def _test(self, website, sample_url):
        print "\n-------------------------------Report results for %s-------------------------------" % website
        print ">>>>>>sample url: %s" % sample_url

        today = date.today()

        base = "http://localhost/get_data?url=%s"
        test_json = requests.get(base%(urllib.quote(sample_url))).text

        try:
            test_json = json.loads(test_json)
            test_json_str = json.dumps(test_json, sort_keys=True, indent=4)

            if "sellers" not in test_json.keys() or "failure_type" in test_json.keys():
                raise Exception("Invalid product")

            self.cur.execute("select * from console_urlsample where website='%s' and url='%s'" % (website, sample_url))
            row = self.cur.fetchall()

            if row:
                row = row[0]

                sample_json = row["json"]
                sample_json_str = row["json"]
                sample_json = json.loads(sample_json)

                print ">>>>>>reports:"

                signal.signal(signal.SIGALRM, signal_handler)
                signal.alarm(30)   # Ten seconds

                try:
                    diff = get_diff(test_json, sample_json)
                except Exception, msg:
                    print "******************Timed out at {0}******************".format(sample_url)
                    print msg

                sql = ("insert into console_reportresult(sample_url, website, "
                       "report_result, changes_in_structure, changes_in_type, changes_in_value, report_date, "
                       "sample_json, current_json) "
                       "values('%s', '%s', $$%s$$, %d, %d, %d, '%s', $$%s$$, $$%s$$)"
                       % (sample_url, website, diff['result'], diff['changes_in_structure'],
                          diff['changes_in_type'], diff['changes_in_value'], today.isoformat(),
                          sample_json_str, test_json_str))

                self.cur.execute(sql)
                self.con.commit()

            self.cur.execute("update console_urlsample set not_a_product=0 where url='%s'" % sample_url)
            self.con.commit()
        except Exception as e:
            print "This url is not valid anymore.\n", e
            self.cur.execute("update console_urlsample set not_a_product=1 where url='%s'" % sample_url)
            self.con.commit()

    def initialize_scraper(self, website):
        # read input urls from database
        today = date.today()

        '''
        self.cur.execute("delete from console_reportresult where report_date='%s' and website='%s'" % (today.isoformat(), website))
        self.con.commit()
        '''

        self.cur.execute("select url_list from console_massurlimport")

        urls = []

        for row in self.cur:
            urls.extend(row[0].splitlines())

        urls = list(set(urls))
        urls = filter(lambda x: website + ".com" in x, urls)

        print "\nRandomly selected urls of %s:" % website
        print '\n' . join(urls)

        print "Loading urls..."

        for url in urls:
            url = url.strip()

            if website in SUPPORTED_SITES:
                self.cur.execute("select not_a_product from console_urlsample where url='%s'" % url)
                row = self.cur.fetchall()

                if not row:
                    try:
                        base = "http://localhost/get_data?url=%s"
                        sample_json = requests.get(base%(urllib.quote(url))).text

                        not_a_product = 0

                        sample_json = json.loads(sample_json)
                        sample_json_str = json.dumps(sample_json, sort_keys=True, indent=4)

                        if "sellers" not in sample_json.keys() or "failure_type" in sample_json.keys():
                            raise Exception('Invalid product')
                    except:
                        not_a_product = 1
                        sample_json_str = ''

                    print url

                    try:
                        self.cur.execute("insert into console_urlsample(url, website, json, qualified_date, not_a_product)"
                                         " values('%s', '%s', $$%s$$, '%s', %d)"
                                         % (url, website, sample_json_str, today.isoformat(), not_a_product))
                        self.con.commit()
                    except:
                        print "******************Parsing Error at {0}******************".format(url)
                        continue

        self.cur.execute("select url from console_urlsample where website = '%s' and not_a_product = 0" % website)
        urls = self.cur.fetchall()

        self.urls_by_scraper[website] = [url[0] for url in urls]
        nTestUrlCounts = len(self.urls_by_scraper[website])

        print "%s - number of test urls : %d" % (website, nTestUrlCounts)


    def test_walmart(self):
        if specified_website and specified_website != "walmart":
            return

        self.initialize_scraper("walmart")

        for url in self.urls_by_scraper["walmart"]:
            try:
                self._test("walmart", url)
            except:
                pass

    def test_amazon(self):
        if specified_website and specified_website != "amazon":
            return

        self.initialize_scraper("amazon")

        for url in self.urls_by_scraper["amazon"]:
            try:
                self._test("amazon", url)
            except:
                pass

    def test_amazon2(self):
        if specified_website and specified_website != "amazon2":
            return

        self.initialize_scraper("amazon2")

        for url in self.urls_by_scraper["amazon2"]:
            try:
                self._test("amazon2", url)
            except:
                pass

    def test_jcpenney(self):
        if specified_website and specified_website != "jcpenney":
            return

        self.initialize_scraper("jcpenney")

        for url in self.urls_by_scraper["jcpenney"]:
            try:
                self._test("jcpenney", url)
            except:
                pass

    def test_kohls(self):
        if specified_website and specified_website != "kohls":
            return

        self.initialize_scraper("kohls")

        for url in self.urls_by_scraper["kohls"]:
            try:
                self._test("kohls", url)
            except:
                pass

    def test_macys(self):
        if specified_website and specified_website != "macys":
            return

        self.initialize_scraper("macys")

        for url in self.urls_by_scraper["macys"]:
            try:
                self._test("macys", url)
            except:
                pass

    def test_target(self):
        if specified_website and specified_website != "target":
            return

        self.initialize_scraper("target")

        for url in self.urls_by_scraper["target"]:
            try:
                self._test("target", url)
            except:
                pass

    def test_uniqlo(self):
        if specified_website and specified_website != "uniqlo":
            return

        self.initialize_scraper("uniqlo")

        for url in self.urls_by_scraper["uniqlo"]:
            try:
                self._test("uniqlo", url)
            except:
                pass

    def test_levi(self):
        if specified_website and specified_website != "levi":
            return

        self.initialize_scraper("levi")

        for url in self.urls_by_scraper["levi"]:
            try:
                self._test("levi", url)
            except:
                pass

    def test_dockers(self):
        if specified_website and specified_website != "dockers":
            return

        self.initialize_scraper("dockers")

        for url in self.urls_by_scraper["dockers"]:
            try:
                self._test("dockers", url)
            except:
                pass

    def test_nike(self):
        if specified_website and specified_website != "nike":
            return

        self.initialize_scraper("nike")

        for url in self.urls_by_scraper["nike"]:
            try:
                self._test("nike", url)
            except:
                pass

    def test_samsclub(self):
        if specified_website and specified_website != "samsclub":
            return

        self.initialize_scraper("samsclub")

        for url in self.urls_by_scraper["samsclub"]:
            try:
                self._test("samsclub", url)
            except:
                pass

    def test_drugstore(self):
        if specified_website and specified_website != "drugstore":
            return

        self.initialize_scraper("drugstore")

        for url in self.urls_by_scraper["drugstore"]:
            try:
                self._test("drugstore", url)
            except:
                pass

if __name__ == '__main__':
    specified_website = ""

    if len(sys.argv) == 2:
        specified_website = sys.argv[1]

    del sys.argv[1:]

    unittest.main()

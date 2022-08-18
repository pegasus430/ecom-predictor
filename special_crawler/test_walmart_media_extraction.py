#!/usr/bin/python

import urllib
import sys
import unittest
import json
import re
import extract_walmart_media
from extract_walmart_data import WalmartScraper

# TODO: fix to work with refactored service code

class ProcessText_test(unittest.TestCase):

    def setUp(self):
        self.urls = filter(None,map(lambda x: x.strip(), sys.stdin.read().splitlines()))

        self.urls_dict = []
        for url in self.urls:
            product = {}
            # product['url'] = url
            # product['page_content'] = urllib.urlopen(url).read()
            # request_url = BASE_URL_VIDEOREQ + _extract_product_id(url)
            # product['response'] = response = urllib.urlopen(request_url).read()
            # self.urls_dict.append(product)

    # def test_errors(self):
    #     for url in self.urls:
    #         args = [1,url] # simlulate sys.argv
    #         result = json.loads(extract_walmart_media.main(args))
    #         self.assertTrue('error' not in result)

    def test_video_if_button(self):
        #for product in self.urls_dict:
        for url in self.urls:

            product = {}
            product['url'] = url
            product['page_content'] = urllib.urlopen(url).read()
            request_url = BASE_URL_VIDEOREQ + _extract_product_id(url)
            product['response'] = response = urllib.urlopen(request_url).read()

            if "'video')" in product['page_content']:
                if 'flv' in product['response']:
                    print "YES", product['url']
                else:
                    print "NO", product['url']

            else:
                if 'flv' in product['response']:
                    print 'no button but video'
                else:
                    print "no button", product['url']

            # if "'video')" in product['page_content']:
            #     self.assertTrue('flv' in product['response'])

    # # test number of media items on page is same as nr of media items in request made at load
    # def test_same_count(self):
    #     for product in self.urls_dict:

    #         #nr_media_page = product['page_content'].count("li onclick=\"WALMART.$('#rmvideoPanel')")
    #         nr_media_page = len(re.findall("WALMART\.\$\('#rmvideoPanel'\)\.richMediaWidget\('click','[^']+','[^']+'\);", product['page_content']))
    #         nr_media_response = product['response'].count("body:")

    #         print product['url'], nr_media_page, nr_media_response
    #         # accept case where there is a video but it's not on the page
    #         if (nr_media_page!=0 or nr_media_response!=1):
    #             self.assertEquals(nr_media_page, nr_media_response)

    # # test if there is extra media judging by result of jsonCallback if there is "video" button but no video
    # def test_extra_media(self):
    #     for product in self.urls_dict:

    #         # has media button
    #         has_media_button = "'video')" in product['page_content']
            
    #         # has response for jsonCallback
    #         has_response = "error" not in product['response']

    #         #print product['url']
    #         # if has_media_button:
    #         #     self.assertTrue(has_response)
    #         if has_media_button and not has_response:
    #             print product['url'], "no response"
    #         if not has_media_button and has_response:
    #             print product['url'], "no media button"


    # def test_button_if_video(self):
    #     for product in self.urls_dict:

    #         if "flv" in product['page_content']:
    #             print "YES", product['url']
    #         else:
    #             print "NO", product['url']

    #         if "flv" in product['response']:
    #             self.assertTrue("'video')" in product['page_content'])


    def tearDown(self):
        pass

if __name__=='__main__':
    unittest.main()
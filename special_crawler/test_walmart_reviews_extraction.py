import unittest
import sys
from extract_walmart_data import WalmartScraper
import json

# TODO: fix to work with refactored service code

class ProcessText_test(unittest.TestCase):

    # create instance variable containing list of urls to be tested, taken from stdin
    def setUp(self):
        self.urls = filter(None,map(lambda x: x.strip(), sys.stdin.read().splitlines()))

    # test that for every input url, reviews were found
    def test_not_null(self):
        for url in self.urls:
            print "On url", url
            response = reviews_for_url(url)

            total_reviews = response['total_reviews']
            average_review = response['average_review']

            self.assertIsNotNone(total_reviews)
            self.assertIsNotNone(average_review)

    # test that average reviews are between 0 and 5
    def test_review_range(self):
        for url in self.urls:
            print "On url", url
            response = reviews_for_url(url)

            average_review = response['average_review']

            try:
                self.assertTrue(float(average_review) >= 0 and float(average_review) <= 5)
            except Exception, e:
                sys.stderr.write("Range test failed for " + average_review + "\n")

if __name__=='__main__':
    unittest.main()

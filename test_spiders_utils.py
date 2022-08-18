import unittest
from spiders_utils import Utils

class ProcessText_test(unittest.TestCase):

    def test_cleanurl(self):
        url = "http://www.target.com#stuff"
        self.assertEquals(Utils.clean_url(url,['#']), "http://www.target.com")

        url = "http://www.amazon.com?stuff"
        self.assertEquals(Utils.clean_url(url), "http://www.amazon.com")

        url = "http://www.amazon.com;stuff"
        self.assertEquals(Utils.clean_url(url), "http://www.amazon.com")


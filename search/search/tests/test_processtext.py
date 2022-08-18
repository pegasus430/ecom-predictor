from nose.tools import assert_true, assert_false, assert_not_equal, assert_equal
import unittest
#from ..spiders.search_spider import ProcessText
from ..spiders.search_spider import ProcessText

class ProcessText_test(unittest.TestCase):

    def test_similar(self):
        text1 = self.p.normalize("one two three one")
        text2 = self.p.normalize("someting one")

        expected_res = 1

        #res = self.p.normalize(text)
        res = self.p.similar_names(text1, text2, 0.4)[0]
        assert_equal(res, expected_res)

    def test_normalize(self):
        # text = "Sony BRAVIA KDL55HX750 55-Inch 240Hz 1080p 3D LED Internet TV, Black"
        # expected_res = ['sony', 'bravia', 'kdl55hx750', '55\"', '240hz', '1080p', '3d', 'led', 'internet', 'tv', 'black', 'kdl55hx75']

        # text = "UN75ES9000F"
        # expected_res = ["un75es9000f", "un75es9000"]
        
        text = "SAMSUNG LARGE FORMAT ED32C 32IN LED 1366X768 4000:1 VGA"
        expected_res = ['samsung', 'large', 'format', 'ed32c', '32\"', 'led', '1366x768', '4000', 'vga']

        res = self.p.normalize(text)
        assert_equal(res, expected_res)

    def test_namewmodel(self):        
        text = ["un75es9000f", "model", "stuff"]
        expected_res = ["un75es9000", "model", "stuff"]

        res = self.p.name_with_alt_modelnr(text)
        assert_equal(res, expected_res)

    def test_altmodel(self):
        text = "sw005"
        expected_res = None

        res = self.p.alt_modelnr(text)
        assert_equal(res, expected_res)


    def setUp(self):
        self.p = ProcessText()

    def tearDown(self):
        pass




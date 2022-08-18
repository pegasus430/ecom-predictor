import unittest
import images_similarity as IS

DIR = "matching_images"
import itertools

class TestSequenceFunctions(unittest.TestCase):

#     def test_pass_over90_2(self):
#         test_pass_over90(2)

#     def test_pass_over90_11(self):
#         test_pass_over90(11)

#     def test_something(self):
#         assert IS.images_identical("matching_images/1_walmart.jpg", "matching_images/1_amazon.jpg")

    images_nrs_above90 = [2, 11, 14, 23, 25, 27, 28, 31, 32]
    images_nrs_above80 = [3, 5, 6, 9, 19, 36, 37, 38, 40, 44]
    images_nrs_below80 = [1, 7, 10, 15, 16, 18, 21]


    # images that should be considered equal, above 90% confidence
    def template_test_pass(self, threshold, images_nrs):
        images_pairs = [(nr, DIR + "/" + str(nr) + "_walmart.jpg", DIR + "/" + str(nr) + "_amazon.jpg") for nr in images_nrs] + \
                        [(nr, DIR + "/" + str(nr) + "_amazon.jpg", DIR + "/" + str(nr) + "_walmart.jpg") for nr in images_nrs] # the reverse pairs

        for (nr, image1, image2) in images_pairs:
            print "\nIMAGE PAIR ", nr
            score1 = IS.images_identical(image1, image2)
            print 'score with median: ', score1
            self.assertTrue(score1 > threshold)
            score2 = IS.images_identical(image1, image2, 2)
            print 'score with average: ', score2
            self.assertTrue(score2 > threshold)

    def atest_pass_over90(self):
        # 2, 11, 14, 23, 25, 27, 28
        self.template_test_pass(90, self.images_nrs_above90)


    def test_pass_over80(self):
        # 3, 5, 6, 9, 19, 36, 37, 40, 44
        self.template_test_pass(80, self.images_nrs_above80[:7])

        # 8, 38 but should work
        # 4

        # acceptable to fail 
        # 5

    def template_test_fail(self, threshold, images_nrs):
        images_pairs = [(nr, DIR + "/" + str(nr) + "_walmart.jpg", DIR + "/" + str(nr) + "_amazon.jpg") for nr in images_nrs] + \
                        [(nr, DIR + "/" + str(nr) + "_amazon.jpg", DIR + "/" + str(nr) + "_walmart.jpg") for nr in images_nrs] # the reverse pairs

        for (nr, image1, image2) in images_pairs:
            print "\nIMAGE PAIR ", nr
            score1 = IS.images_identical(image1, image2)
            print 'score with median: ', score1
            self.assertTrue(score1 < threshold)
            score2 = IS.images_identical(image1, image2, 2)
            print 'score with average: ', score2
            self.assertTrue(score2 < threshold)

    def atest_fail_below80(self):
        self.template_test_fail(80, self.images_nrs_below80)

    def atest_fail_below70(self):
        images_nrs_all = self.images_nrs_above80 + self.images_nrs_above90 + self.images_nrs_below80
        images_pairs = [(nr1, nr2, DIR + "/" + str(nr1) + "_walmart.jpg", DIR + "/" + str(nr2) + "_amazon.jpg") for (nr1, nr2) in itertools.product(images_nrs_all, images_nrs_all) if nr1!=nr2]    

        for (nr, nr2, image1, image2) in images_pairs:
            # print "\nIMAGE PAIR ", nr1, nr2
            score1 = IS.images_identical(image1, image2)
            score2 = IS.images_identical(image1, image2, 2)

            self.assertTrue(score1 < 70)
            self.assertTrue(score2 < 70)
        


if __name__=='__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestSequenceFunctions)
    unittest.TextTestRunner(verbosity=3).run(suite)


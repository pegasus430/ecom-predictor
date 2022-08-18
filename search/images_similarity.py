#!/usr/bin/python

import cv2
import numpy
import sys
import math

numpy.set_printoptions(threshold=numpy.nan)

def segment(im):

    gray = cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
    #blur = cv2.GaussianBlur(gray,(5,5),0)

    _,thresh = cv2.threshold(gray,220,255,cv2.THRESH_BINARY_INV)
    #thresh = cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY_INV,25,2)

    cv2.imwrite('thresh.jpg', thresh)

    # #################      Now finding Contours         ###################
    # kernel = cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))

    # #TODO: try to vary iterations
    # thresh = cv2.erode(thresh,kernel,iterations = 1)

    #cv2.imwrite('thresh.jpg', thresh)
    contours,hierarchy = cv2.findContours(thresh,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)

    #i=0
    rois = []
    im2 = numpy.copy(im)
    for cnt in contours:
      
        #print "area above 50"
        [x,y,w,h] = cv2.boundingRect(cnt)

        # reject subimages with height or width below 5 pixels
        if (h<5) or (w<5):
            continue

        #print "height above 10"
        
        cv2.rectangle(im2,(x,y),(x+w,y+h),(0,0,255),2)
    
        roi = im[y:y+h,x:x+w]

        # if y>5 and x>5:
        #     roi = gray[y-5:y+h+5,x-5:x+w+5]

        # store roi and x coordinate to sort by
        rois.append((roi, x))
        # cv2.imwrite('letter'+str(i)+'.jpg',roi)
        # i+=1

        # roismall = cv2.resize(roi,(10,10))

    cv2.imwrite('segmented.jpg', im2)

    # sort rois by size
    #TODO: correct?
    ret = map(lambda x: x[0],sorted(rois, key=lambda x: -len(x[0])))
    #print map(lambda x: len(x), ret)

    return ret[0]


# add borders to the image up to a size
def add_borders(image, target_height, target_width):

    height, width, depth = image.shape
    width_pad = (target_width - width) / 2.0
    left_pad = int(width_pad)

    # make sure rounding didn't affect the desired final size of the picture (=self.HEIGHTxself.WIDTH)
    # if it was not an integer (so .5), add 1 to the opposite pad
    if (left_pad != width_pad):
        right_pad = left_pad+1
    else:
        right_pad = left_pad

    height_pad = (target_height - height) / 2.0
    top_pad = int(height_pad)
    # if it was not an integer (so .5), add 1 to the opposite pad
    if (top_pad!=height_pad):
        bottom_pad = top_pad+1
    else:
        bottom_pad = top_pad

    # if all borders are positive
    if height_pad > 0 and width_pad > 0:
        dst = cv2.copyMakeBorder(image, top_pad, bottom_pad, left_pad, right_pad, cv2.BORDER_CONSTANT, value=0)
    # else just resize
    else:    
        dst = cv2.resize(image,(target_height,target_width))
        sys.stderr.write("Could not add borders, shape " + str(height) + "," + str(width) + "\n")
    return dst


# tests if 2 images given by their filenames are the same
# returns a confidence score
# method: 1 - use median of pixels, 2 - use average of pixels
def images_identical(image_name1, image_name2, method=1):

    image1 = cv2.imread(image_name1)
    image2 = cv2.imread(image_name2)

    # #TODO: fix this for images where it's not clear which is bigger
    # # image1 should be the bigger image
    # if image1.shape[0] < image2.shape[0]:
    #     print "image1 is smaller"
    #     image1, image2 = image2, image1


    # normalize size
    image1 = segment(image1)
    image2 = segment(image2)

    # get image size
    height, width, depth = image1.shape

    image2 = cv2.resize(image2, (width, height))
    #image2 = add_borders(image2, height, width)

    # convert to gray
    image1 = cv2.cvtColor(image1,cv2.COLOR_BGR2GRAY)
    image2 = cv2.cvtColor(image2,cv2.COLOR_BGR2GRAY)

    cv2.imwrite("i1.jpg", image1)
    cv2.imwrite("i2.jpg", image2)

    # normalize contrast
    image1 = cv2.equalizeHist(image1)
    image2 = cv2.equalizeHist(image2)

    cv2.imwrite("equalizedi1.jpg", image1)
    cv2.imwrite("equalizedi2.jpg", image2)

    # build numpy array the size of the images, with all values = 255 - if it equals compare's result, it means the images were identical
    #test_array = numpy.array([[[255] * depth] * width] * height)
    test_array = numpy.array([[255] * width] * height)
    comp_result = cv2.compare(image1, image2, cv2.CMP_EQ)

    # array of differences in pixel intensities between the 2 images
    differences = []

    # test image with black where they match
    test_image = numpy.copy(image1)
    for i1 in range(test_image.shape[0]):
        for i2 in range(test_image.shape[1]):
            # for i3 in range(test_image.shape[2]):
            #     if comp_result[i1][i2][i3] == 255:
            #         test_image[i1][i2][i3] = 255
            #if comp_result[i1][i2] == 225:
            difference = math.fabs(float(image2[i1][i2]) - float(image1[i1][i2]))
            differences.append(difference)
            test_image[i1][i2] = difference
            # if comp_result[i1][i2] ==255:
            #     test_image[i1][i2] = image1[i1][i2] - image2[i1][i2]
    cv2.imwrite("test_image.jpg", test_image)

    # for nr in differences:
    #     print nr

    assert test_array.shape == comp_result.shape
    #print test_array.shape, comp_result.shape

    # build matrix with 'True' where they match and 'False' where they don't
    equality_matrix = (comp_result == test_array)

    # count number of matching cells
    matched_cells = equality_matrix.sum()

    # count total number of cells
    total_cells = reduce(lambda x, y: x*y, test_array.shape)

    # compute percent of matched cells
    percent_matched = float(matched_cells)/total_cells*100

    #print matched_cells, total_cells

    #return numpy.array_equal(comp_result, test_array)


    #TODO: experiment with median vs average
    # maybe include some way of enforcing perfectly identical pixels. or very very close. hm. i guess that's what median does?
    if method==2:
        #print 'average', numpy.average(differences), 'score', (255.0 - numpy.average(differences)) / 255 * 100
        medium_difference = numpy.average(differences)
    if method==1:
        #print 'median', numpy.median(differences), 'score', (255.0 - numpy.median(differences)) / 255 * 100
        medium_difference = numpy.median(differences)


    # compute confidence score for match
    score = (255.0 - medium_difference) / 255 * 100
    return score

if __name__=='__main__':

    print images_identical(sys.argv[1], sys.argv[2], 2)
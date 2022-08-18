import os
import cv2
from PIL import Image
import urllib
import re
import cStringIO
import numpy as np
from StringIO import StringIO


def get_calcHist(hsv):
    return cv2.calcHist( [hsv], [0, 1], None, [180, 256], [0, 180, 0, 256] )


def url_to_image(url):
    # download the image, convert it to a NumPy array, and then read
    # it into OpenCV format
    resp = urllib.urlopen(url)
    image = np.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


def compare_images(img1, img2):
    """ Takes 2 images, as local paths or URLs.
        Returns a float [0, 1) representing the similarities of the images.
    """
    hist = []
    for image in  (img1, img2):
        path, ext = os.path.splitext(image)
        path += ".jpg"

        is_local = os.path.isfile(image)
        img = None
        if bool(re.findall("^[a-zA-Z]+://", image)):
            # file = cStringIO.StringIO(urllib.urlopen(image).read())
            img = url_to_image(image)

        if ext not in (".jpg", ".jpeg", ".png"):
            if is_local:
                Image.open(path).convert('RGB').save(path)
                img = cv2.imread(path)
            else:
                im = Image.open(StringIO(urllib.urlopen(image).read()))
                file_mem = StringIO()
                im.convert('RGB').save(file_mem, format="PNG")
                file_mem.seek(0)
                img_array = np.asarray(bytearray(file_mem.read()), dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                file_mem.close()
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist.append(get_calcHist(hsv))

    # Test all 4 comparison methods? iterate over methods in cycle
    #for i in range(0, 4):
    #    comp = cv2.compareHist(hist[0], hist[1], i)
    #    print comp

    correlation = cv2.compareHist(hist[0], hist[1], 0)
    return correlation


if __name__ == '__main__':
    i2 = 'http://www.viralnovelty.net/wp-content/uploads/2014/07/121.jpg'
    i1 = 'http://upload.wikimedia.org/wikipedia/commons/3/36/Hopetoun_falls.jpg'
    # i1 = 'http://www.w3schools.com/html/html5.gif'

    print compare_images(i1, i2)
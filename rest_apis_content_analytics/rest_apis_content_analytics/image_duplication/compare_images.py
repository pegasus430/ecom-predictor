import cv2
from PIL import Image
import urllib
import numpy as np


def get_calcHist(hsv):
    return cv2.calcHist( [hsv], [0, 1], None, [180, 256], [0, 180, 0, 256] )


def url_to_image(url):
    # download the image, convert it to a NumPy array, and then read
    # it into OpenCV format
    resp = urllib.urlopen(url)
    image = np.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
    return image


def compare_two_images_a(img1, img2):
    """ Takes 2 images, as local paths or URLs.
        Returns a float [0, 1) representing the similarities of the images.
    """
    hist = []

    hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

    hist.append(get_calcHist(hsv1))
    hist.append(get_calcHist(hsv2))

    correlation = cv2.compareHist(hist[0], hist[1], 0)

    return correlation


def get_thumbnail(image, size=(64,64), stretch_to_fit=False, greyscale=False):
    " get a smaller version of the image - makes comparison much faster/easier"
    if not stretch_to_fit:
        image.thumbnail(size, Image.ANTIALIAS)
    else:
        image = image.resize(size); # for faster computation
    if greyscale:
        image = image.convert("L")  # Convert it to grayscale.
    return image


def compare_two_images_c(image1, image2):
    # source: http://www.syntacticbayleaves.com/2008/12/03/determining-image-similarity/
    # may throw: Value Error: matrices are not aligned .
    from numpy import average, linalg, dot

    image1 = get_thumbnail(image1, stretch_to_fit=True)
    image2 = get_thumbnail(image2, stretch_to_fit=True)

    images = [image1, image2]
    vectors = []
    norms = []
    for image in images:
        vector = []
        for pixel_tuple in image.getdata():
            vector.append(average(pixel_tuple))
        vectors.append(vector)
        norms.append(linalg.norm(vector, 2))
    a, b = vectors
    a_norm, b_norm = norms
    # ValueError: matrices are not aligned !
    if a_norm == b_norm == 0:
        # black images
        return 1
    else:
        res = dot(
            (a / a_norm) if a_norm else a,
            (b / b_norm) if b_norm else b
        )

    return res


def compare_two_images_b(img1, img2):
    hash1 = dhash(img1)
    hash2 = dhash(img2)

    return float(float((len(hash1) - hamming_distance(hash1, hash2))) / len(hash1))


def hamming_distance(s1, s2):
    """Return the Hamming distance between equal-length sequences"""
    if len(s1) != len(s2):
        raise ValueError("Undefined for sequences of unequal length")
    return sum(ch1 != ch2 for ch1, ch2 in zip(s1, s2))


def dhash(image, hash_size=16):
    # Grayscale and shrink the image in one step.
    image = image.convert('L').resize(
        (hash_size, hash_size),
        Image.BILINEAR,
    )

    # Compare adjacent pixels.
    difference = []
    for row in xrange(hash_size):
        for col in xrange(hash_size - 1):
            pixel_left = image.getpixel((col, row))
            pixel_right = image.getpixel((col + 1, row))
            difference.append(pixel_left > pixel_right)

    # Convert the binary array to a hexadecimal string.
    decimal_value = 0
    hex_string = []
    for index, value in enumerate(difference):
        if value:
            decimal_value += 2**(index % 8)
        if (index % 8) == 7:
            hex_string.append(hex(decimal_value)[2:].rjust(2, '0'))
            decimal_value = 0

    return ''.join(hex_string)
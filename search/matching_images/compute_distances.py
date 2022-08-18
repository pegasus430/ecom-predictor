import distance
import re
from imagehash import phash
import cv2
import numpy as np
import sys
from matplotlib import pyplot as plt
import numpy
from PIL import Image
from blockhash import blockhash
from itertools import product
from collections import OrderedDict

image_hashes_a = {}
image_hashes_w = {}
image_hists_a = {}
image_hists_w = {}

closest = []

def hash_hamming(h1, h2):
    '''Hamming distance between two hashes, convert to binary first'''
    # convert to binary and pad up to 256 bits
    b1 = bin(int(h1,16))[2:].zfill(256)
    b2 = bin(int(h2,16))[2:].zfill(256)
    return distance.hamming(b1,b2)

def hash_similarity(h1, h2, bits=16):
    '''Similarity between 2 hashes (0-100), based on hamming distance
    Hashes are assumed to be 64-char long (256 bits)
    '''
    d = hash_hamming(h1, h2)
    s = 100 - (d/float(bits*4*4))*100
    return s

def compute_histogram(image, equalize=False, bins=8, trunc_bins=False):
    # image = cv2.imread(image_path)
    if equalize:
        image = equalize_hist_color(image)
    hist = cv2.calcHist([image], [0, 1, 2], None, [bins, bins, bins],[0, 256, 0, 256, 0, 256])
    if trunc_bins:
        hist = numpy.array(sorted(hist.flatten(), reverse=True)[:100])
    else:
        hist = numpy.array(hist.flatten())

    return hist   

def histogram_similarity(image1, image2, bins=8, trunc_bins=False):
    '''Input are 2 opencv images, output is histogram similarity
    '''
    hist1 = compute_histogram(image1, equalize=False, bins=8, trunc_bins=False)
    hist1 = compute_histogram(image2, equalize=False, bins=8, trunc_bins=False)
    # print hist1
    # print hist2
    score = cv2.compareHist(hist1, hist2, cv2.cv.CV_COMP_CORREL)
    return score * 100

def image_histogram_to_string(image, equalize=True):
    '''Take an image, compute its color histogram,
    flatten it to a list and then output it to a comma-separated string
    '''
    hist = compute_histogram(image, equalize)
    histf = cv2.normalize(hist).flatten()
    lhistf = list(histf)
    hists = ','.join(map(str,lhistf))
    return hists

def histogram_to_string(hist):
    '''Take a histogram (numpy array)
    flatten it to a list and then output it to a comma-separated string
    '''
    histf = cv2.normalize(hist).flatten()
    lhistf = list(histf)
    hists = ','.join(map(str,lhistf))
    return hists


def equalize_hist_color(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2YCR_CB)
    channels = cv2.split(image)
    channels[0] = cv2.equalizeHist(channels[0])
    image = cv2.merge(channels)
    image = cv2.cvtColor(image, cv2.COLOR_YCR_CB2BGR)
    return image

def shistogram_similarity(hstr1, hstr2):
    '''Input strings representing flattened histograms
    Output similarity
    '''

    h1 = np.array(map(float,hstr1.split(','))).astype(np.float32)
    h2 = np.array(map(float,hstr2.split(','))).astype(np.float32)

    try:
        s = cv2.compareHist(h1,h2,cv2.cv.CV_COMP_CORREL)
    except Exception, e:
        sys.stderr.write(str(e) + "\n")
        return 0

    return s*100

def combined_similarity(hash1, hash2, hist1, hist2):
    s1 = hash_similarity(hash1, hash2)
    s2 = shistogram_similarity(hist1, hist2)
    return (s1+s2)/2.

def compute_similarities():
    with open("image_blockhashes_nows.txt") as fin:
        for line in fin:
            image, hashv = line.split()
            if image.startswith("nows"):
                nows, imagenr, site = image.split("_")
            else:
                imagenr, site = image.split("_")
            if site.startswith("amazon"):
                image_hashes_a[image] = hashv
            if site.startswith("walmart"):
                image_hashes_w[image] = hashv

    with open("image_histograms_nows.txt") as fin:
        for line in fin:
            image, hist = line.split()
            if image.startswith("nows"):
                nows, imagenr, site = image.split("_")
            else:
                imagenr, site = image.split("_")
            if site.startswith("amazon"):
                image_hists_a[image] = hist
            if site.startswith("walmart"):
                image_hists_w[image] = hist


    print "image,most_similar,match,most_similar_similarity,match_similarity,hash_similarity,shistogram_similarity"
    for image in image_hashes_w:
        most_similar = max(image_hashes_a.keys(), key=lambda i:\
            # shistogram_similarity(image_hashes_w[image], image_hashes_a[i]))
            combined_similarity(image_hashes_w[image], image_hashes_a[i], image_hists_w[image], image_hists_a[i]))
        image_match = re.sub("walmart", "amazon", image)
        
        try:
            closest.append((image, most_similar, \
                image_match,\
                combined_similarity(image_hashes_w[image], image_hashes_a[most_similar], image_hists_w[image], image_hists_a[most_similar]), \
                combined_similarity(image_hashes_w[image], image_hashes_a[image_match], image_hists_w[image], image_hists_a[most_similar]), \
                hash_similarity(image_hashes_w[image], image_hashes_a[image_match]), \
                shistogram_similarity(image_hists_w[image], image_hists_a[image_match])))

        except Exception, e:
            sys.stderr.write(str(e))

    for t in closest:
        print ",".join(map(str, t))


    # average_distance = sum([(t[3]+t[4])/2. for t in closest])/len(closest)
    # for how many the most similar was the actual match
    # nows images
    accuracy1 = len(filter(lambda t: t[0].split("_")[1]==t[1].split("_")[1], closest)) / float(len(closest))
    # normal images
    # accuracy1 = len(filter(lambda t: t[0].split("_")[0]==t[1].split("_")[0], closest)) / float(len(closest))
    print accuracy1
    # for how many the similarity with the actual match was > threshold
    accuracy2 = len(filter(lambda t: t[4] > 70, closest)) / float(len(closest))
    print accuracy2

def draw_histogram(image_path):
    image = cv2.imread(image_path)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2YCR_CB)
    channels = cv2.split(image)
    hist = compute_histogram(image_path, equalize=False)
    # plt.axis([0, 256, 0, 300])

    plt.hist(channels[0], bins=8)
    plt.savefig("/tmp/hist_" + image_path)
    plt.clf()
    plt.close()

    image = equalize_hist_color(image)
    channels = cv2.split(image)
    histeq = compute_histogram(image_path, equalize=False)
    plt.hist(channels[0], bins=8)
    plt.savefig("/tmp/hist_" + image_path[:-4] + "_eq.jpg")
    plt.clf()

    plt.close()

def _show(image):
    cv2.imshow("image", image)
    cv2.waitKey(0)

def _blockhash(image, bits = 16, resize256=True):
    '''
    :param bits: number of bits for the hash
    :param resize256: whether to resize both images to 256x256
    '''

    if resize256 == 1:
        image = cv2.resize(image, (256, 256))

    pilimage = Image.fromarray(image)
    bhash = blockhash(pilimage, bits)
    return bhash

def blockhash_similarity(image1, image2, bits=16, resize=2):
    '''
    :param resize: resize option
    None: don't resize
    1: resize to image1's size
    2: resize to fixed size of 256x256
    '''
    if resize:
        if resize == 1:
            image2 = cv2.resize(image2, (image1.shape[1], image2.shape[0]))
        if resize == 2:
            image1 = cv2.resize(image1, (256, 256))
            image2 = cv2.resize(image2, (256, 256))
    h1 = _blockhash(image1, bits)
    h2 = _blockhash(image2, bits)
    return hash_similarity(h1, h2, bits)

def images_similarity(image1_path, image2_path, hist_weight=.8, bh_bits=16, blur=True, \
    threshold_light=True, hist_bins=8, trunc_bins=True, wsthresh_val=230):
    '''Computes similarity between 2 images (opencv data structures)
    :param weight: weight of histogram similarity vs hash similarity
    :param bh_bits: nr bits used for blockhash
    :param blur: blur (remove noise) images first
    :param threhsold_light: remove very light pixes (replace them with white) first
    '''

    image1 = cv2.imread(image1_path)
    image2 = cv2.imread(image2_path)
    
    stdsize = (image1.shape[1], image1.shape[0])
    image1 = _normalize_image(image1, blur, threshold_light, wsthresh_val=wsthresh_val)
    image2 = _normalize_image(image2, stdsize, blur, threshold_light, wsthresh_val=wsthresh_val)

    # 5. compare histograms
    shistogram_similarity = histogram_similarity(image1, image2, bins=hist_bins, trunc_bins=trunc_bins)

    # 6. blockhash similarity
    hash_similarity = blockhash_similarity(image1, image2, bh_bits)

    # compute average
    sys.stderr.write("Hist sim: " + str(shistogram_similarity) + " Hash sim: " + str(hash_similarity) + "\n")
    hash_weight = 1 - hist_weight
    avg_similarity = hist_weight * shistogram_similarity + hash_weight * hash_similarity
    return avg_similarity

def _normalize_image(image, size=None, blur=False, threshold_light=True, wsthresh_val=230):
    # image = cv2.imread(image_path)
    
    if blur:
        image = cv2.GaussianBlur(image,(3,3),0)
    
    # 1. threshold off-white pixels
    if threshold_light:
        image = _threshold_light(image)

    # 2. remove white borders
    image = _remove_whitespace(image, thresh_val=wsthresh_val)


    # # 3. resize to same size
    # if size and size!= (image.shape[1], image.shape[0]):
    #     image = cv2.resize(image, size)    

    # 4. equalize color histogram
    image = equalize_hist_color(image)
    # _show(image)
    return image

def _threshold_light(image):
    '''Threshold pixels close to white (very light greys),
    set them to white
    '''
    THRESH = 230
    # TODO try adaptive threshold?
    image[numpy.where(image > THRESH)] = 255
    return image

def _remove_whitespace(image, thresh_val=230):
    '''Crop image to remove whitespace around object
    '''

    imagec = numpy.copy(image)
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    _,thresh = cv2.threshold(gray,thresh_val,255,cv2.THRESH_BINARY_INV)
    contours,hierarchy = cv2.findContours(thresh,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)

    rois = []

    for cnt in contours:
        [x,y,w,h] = cv2.boundingRect(cnt)
        if (h<5) or (w<5):
            continue
        cv2.rectangle(imagec,(x,y),(x+w,y+h),(0,0,255),2)
        roi = image[y:y+h,x:x+w]

        # if y>5 and x>5:
        #     roi = gray[y-5:y+h+5,x-5:x+w+5]

        # store roi and x coordinate to sort by
        rois.append((roi, x))

    # sort rois by size
    ret = map(lambda x: x[0],sorted(rois, key=lambda x: -len(x[0])))
    return ret[0]

def benchmark(image_nr=None):
    features = {
    'threshold_light' : [True, False], \
    'bh_bits' : [8, 16, 32], \
    'trunc_bins' : [True, False], \
    'hist_weight' : [.2, .3, .4, .5, .6, .7, .8, .9], \
    'hist_bins' : [8, 16, 32, 50, 100], \
    'blur' : [True, False], \
    'wsthresh_val' : [200, 205, 210, 220, 230, 240]
    }

    param_features = ['blur', 'hist_weight']

    results = {k1 : \
                {k2 : 0 for k2 in features[param_features[0]]} \
            for k1 in features[param_features[1]]}

    param_ranges = [features[f] for f in param_features]
    current_params = {}
    for currvalues in product(*param_ranges):
        for i, f in enumerate(param_features):
            current_params[f] = currvalues[i]

        print current_params
        avg_sim = 0
        accuracy = 0
        nr_images = 0
        if image_nr:
            test_set = [image_nr]
        else:
            test_set = range(50)
        for nr in test_set:
            print "Image", nr
            s = 0
            ss = []
            # Check if the highest score is between this image and its match or another => measure accuracy
            for nr2 in range(50):
                try:
                    s = images_similarity("%s_walmart.jpg" % str(nr), "%s_amazon.jpg" % str(nr2), **current_params)
                    ss.append((nr2, s))
                except:
                    pass
                    continue
            if ss:
                ss = sorted(ss, key=lambda t: t[1], reverse=True)
                # max score for its match (same number)
                
                print "Most similar:", ss[0][0]
                if int(ss[0][0]) == int(nr):
                    accuracy += 1
                # if anything happened at all
                nr_images += 1
            # avg_sim += s
        avg_sim = avg_sim / nr_images
        accuracy = float(accuracy) / nr_images
        # print "Similarity:", avg_sim, "\n"
        print "Accuracy:", accuracy, "\n"
        # results[current_params[param_features[1]]][current_params[param_features[0]]] = avg_sim
        results[current_params[param_features[1]]][current_params[param_features[0]]] = accuracy


    # draw heatmap
    
    data = numpy.array([r.values() for r in results.values()])
    print results
    fig, ax = plt.subplots()
    heatmap = ax.pcolor(data)
    plt.colorbar(heatmap)
    # row_labels = [param_features[0] + ": " + str(b) for b in features[param_features[0]]]
    row_labels = [param_features[0] + ": " + str(b) for b in results.values()[0].keys()]
    # column_labels = [param_features[1] + ": " + str(w) for w in features[param_features[1]]]
    column_labels = [param_features[1] + ": " + str(w) for w in results.keys()]
    ax.set_yticks(np.arange(data.shape[0])+0.5, minor=False)
    ax.set_xticks(np.arange(data.shape[1])+0.5, minor=False)
    ax.set_xticklabels(row_labels, minor=False)
    ax.set_yticklabels(column_labels, minor=False)
    plt.show()
    if image_nr:
        plt.savefig("/tmp/benchmark_%s.png" % str(image_nr))


if __name__=="__main__":
    import sys
    # # compute_similarities()
    # for i in [36, 38, 40, 31, 48]:
    #     image1 = "nows_%s_amazon.jpg" % str(i)
    #     image2 = "nows_%s_walmart.jpg" % str(i)
    #     draw_histogram(image1)
    #     draw_histogram(image2)

    nr = sys.argv[1]
    # for nr in range(50):
    #     try:
    #         im1 = "%s_walmart.jpg" % str(nr)
    #         im2 = "%s_amazon.jpg" % str(nr)
    #         s = images_similarity(im1, im2)
    #         print ",".join([im1, im2, str(s)])
    #     except Exception, e:
    #         sys.stderr.write(str(e))
    #         pass

    benchmark()
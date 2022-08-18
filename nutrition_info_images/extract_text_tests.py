import cv2.cv as cv
import cv2
import pytesseract
from PIL import Image
import urllib, urllib2
import cStringIO # *much* faster than StringIO
import numpy as np
from nltk.corpus import wordnet
import itertools
from memory_profiler import profile

@profile
def preprocessing1(src, debug=False, gblur1_param1=5, ablur_param1=1, ablur_param2=75,\
    dilate_param=1, erode_param=2, morph_el=1, thresh_param1=15, thresh_param2=2, thresh_param3=170,\
    image_size=1500):
    '''Preprocess input image, using some order of the preprocessing operations
    (version 1)
    '''
    # resize image
    orig_size = src.shape[:2]
    # such that smaller dimension is 1000 pixels at least
    normalized_size = max(image_size, max(orig_size))
    max_dim_idx = max(enumerate(orig_size), key=lambda l: l[1])[0]
    min_dim_idx = [idx for idx in [0,1] if idx!=max_dim_idx][0]
    new_size = [0,0]
    new_size[min_dim_idx] = normalized_size
    new_size[max_dim_idx] = int(float(orig_size[max_dim_idx]) / orig_size[min_dim_idx] * normalized_size)

    src = cv2.resize(src=src, dsize=tuple(new_size), dst=src, fx=0, fy=0)
    
    # erode + dilate
    strelem = {1:cv2.MORPH_CROSS, 2:cv2.MORPH_RECT, 3:cv2.MORPH_ELLIPSE}
    element = cv2.getStructuringElement(strelem[morph_el],(erode_param*2+1,erode_param*2+1))
    element2 = cv2.getStructuringElement(strelem[morph_el],(dilate_param*2+1,dilate_param*2+1))
    skel = np.zeros(src.shape,np.uint8)

    eroded = cv2.erode(src,element)
    if debug:
        cv2.imwrite("/tmp/3eroded.png", eroded)
    temp = cv2.dilate(eroded,element2)
    if debug:
        cv2.imwrite("/tmp/4dilated.png", temp)

    src = temp

    # # black and white
    src = cv2.adaptiveThreshold(src, 255, adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C, thresholdType=cv2.THRESH_BINARY, \
        blockSize=2*thresh_param1+1, C=thresh_param2)
    # # _, src = cv2.threshold(src, 150, 255, cv2.THRESH_BINARY)
    # # For large text I think we need the first parameter to be higher
    # src = cv2.adaptiveThreshold(src,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,23,3)
    # # _,src = cv2.threshold(src,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    # if debug:
    #     cv2.imwrite("/tmp/5thresh.png", src)
    
    return src
            

@profile
def preprocessing2(src, debug=False, gblur1_param1=5, ablur_param1=1, ablur_param2=75,\
    dilate_param=1, erode_param=2, morph_el=1, thresh_param1=15, thresh_param2=2, thresh_param3=170,\
    image_size=1500):
    '''Preprocess input image, using some order of the preprocessing operations
    '''
    
    # resize image to 4 times original size
    src = cv2.resize(src=src, dsize=(0,0), dst=src, fx=4, fy=4)

    # # smooth
    # # src = cv2.GaussianBlur(src,(5,5),0)
    # src = cv2.adaptiveBilateralFilter(src,(1,1),75,75)
    # cv2.imwrite("/tmp/2blurred2.png", src)
    
    # erode + dilate
    strelem = {1:cv2.MORPH_CROSS, 2:cv2.MORPH_RECT, 3:cv2.MORPH_ELLIPSE}
    element = cv2.getStructuringElement(strelem[morph_el],(erode_param*2+1,erode_param*2+1))
    element2 = cv2.getStructuringElement(strelem[morph_el],(dilate_param*2+1,dilate_param*2+1))
    skel = np.zeros(src.shape,np.uint8)

    eroded = cv2.erode(src,element)
    if debug:
        cv2.imwrite("/tmp/3eroded.png", eroded)
    temp = cv2.dilate(eroded,element2)
    if debug:
        cv2.imwrite("/tmp/4dilated.png", temp)
    # temp = cv2.subtract(src,temp)
    # skel = cv2.bitwise_or(skel,temp)
    src = temp

    # # black and white
    src = cv2.adaptiveThreshold(src, 255, adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C, thresholdType=cv2.THRESH_BINARY, \
    blockSize=thresh_param1*2+1, C=thresh_param2)
 
    return src


@profile
def preprocessing3(src, debug=False, gblur1_param1=5, ablur_param1=1, ablur_param2=75,\
    dilate_param=1, erode_param=2, morph_el=1, thresh_param1=15, thresh_param2=2, thresh_param3=170,\
    image_size=1500):
    '''Preprocess input image, using some order of the preprocessing operations
    '''

    # resize image
    orig_size = src.shape[:2]
    # such that smaller dimension is 1000 pixels at least
    normalized_size = max(image_size, max(orig_size))
    max_dim_idx = max(enumerate(orig_size), key=lambda l: l[1])[0]
    min_dim_idx = [idx for idx in [0,1] if idx!=max_dim_idx][0]
    new_size = [0,0]
    new_size[min_dim_idx] = normalized_size
    new_size[max_dim_idx] = int(float(orig_size[max_dim_idx]) / orig_size[min_dim_idx] * normalized_size)

    src = cv2.resize(src=src, dsize=tuple(new_size), dst=src, fx=0, fy=0)
    
    # erode + dilate
    strelem = {1:cv2.MORPH_CROSS, 2:cv2.MORPH_RECT, 3:cv2.MORPH_ELLIPSE}
    element = cv2.getStructuringElement(strelem[morph_el],(erode_param*2+1,erode_param*2+1))
    element2 = cv2.getStructuringElement(strelem[morph_el],(dilate_param*2+1,dilate_param*2+1))
    skel = np.zeros(src.shape,np.uint8)

    eroded = cv2.erode(src,element)
    if debug:
        cv2.imwrite("/tmp/3eroded.png", eroded)
    temp = cv2.dilate(eroded,element2)
    if debug:
        cv2.imwrite("/tmp/4dilated.png", temp)

    src = temp

    # black and white
    _,src = cv2.threshold(src,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    if debug:
        cv2.imwrite("/tmp/5thresh.png", src)
    
        
    return src

@profile
def preprocessing4(src, debug=False, gblur1_param1=5, ablur_param1=1, ablur_param2=75,\
    dilate_param=1, erode_param=2, morph_el=1, thresh_param1=15, thresh_param2=2, thresh_param3=170,\
    image_size=1500):
    '''Preprocess input image, using some order of the preprocessing operations
    '''

    # resize image
    orig_size = src.shape[:2]
    # such that smaller dimension is 1000 pixels at least
    normalized_size = max(image_size, max(orig_size))
    max_dim_idx = max(enumerate(orig_size), key=lambda l: l[1])[0]
    min_dim_idx = [idx for idx in [0,1] if idx!=max_dim_idx][0]
    new_size = [0,0]
    new_size[min_dim_idx] = normalized_size
    new_size[max_dim_idx] = int(float(orig_size[max_dim_idx]) / orig_size[min_dim_idx] * normalized_size)

    src = cv2.resize(src=src, dsize=tuple(new_size), dst=src, fx=0, fy=0)
    
    # erode + dilate
    strelem = {1:cv2.MORPH_CROSS, 2:cv2.MORPH_RECT, 3:cv2.MORPH_ELLIPSE}
    element = cv2.getStructuringElement(strelem[morph_el],(erode_param*2+1,erode_param*2+1))
    element2 = cv2.getStructuringElement(strelem[morph_el],(dilate_param*2+1,dilate_param*2+1))
    skel = np.zeros(src.shape,np.uint8)

    eroded = cv2.erode(src,element)
    if debug:
        cv2.imwrite("/tmp/3eroded.png", eroded)
    temp = cv2.dilate(eroded,element2)
    if debug:
        cv2.imwrite("/tmp/4dilated.png", temp)

    src = temp

    # black and white
    _, src = cv2.threshold(src, thresh_param3, 255, cv2.THRESH_BINARY)
    if debug:
        cv2.imwrite("/tmp/5thresh.png", src)
    
        
    return src

@profile
def preprocessing5(src, debug=False, gblur1_param1=5, ablur_param1=1, ablur_param2=75,\
    dilate_param=1, erode_param=2, morph_el=1, thresh_param1=15, thresh_param2=2, thresh_param3=170,\
    image_size=1500):
    '''Preprocess input image, using some order of the preprocessing operations
    (like first but no thresholding)
    '''
    # resize image
    orig_size = src.shape[:2]
    # such that smaller dimension is 1000 pixels at least
    normalized_size = max(image_size, max(orig_size))
    max_dim_idx = max(enumerate(orig_size), key=lambda l: l[1])[0]
    min_dim_idx = [idx for idx in [0,1] if idx!=max_dim_idx][0]
    new_size = [0,0]
    new_size[min_dim_idx] = normalized_size
    new_size[max_dim_idx] = int(float(orig_size[max_dim_idx]) / orig_size[min_dim_idx] * normalized_size)

    src = cv2.resize(src=src, dsize=tuple(new_size), dst=src, fx=0, fy=0)
    
    # erode + dilate
    strelem = {1:cv2.MORPH_CROSS, 2:cv2.MORPH_RECT, 3:cv2.MORPH_ELLIPSE}
    element = cv2.getStructuringElement(strelem[morph_el],(erode_param*2+1,erode_param*2+1))
    element2 = cv2.getStructuringElement(strelem[morph_el],(dilate_param*2+1,dilate_param*2+1))
    skel = np.zeros(src.shape,np.uint8)

    eroded = cv2.erode(src,element)
    if debug:
        cv2.imwrite("/tmp/3eroded.png", eroded)
    temp = cv2.dilate(eroded,element2)
    if debug:
        cv2.imwrite("/tmp/4dilated.png", temp)

    src = temp

    return src

def is_dictionary_word(word):
    if wordnet.synsets(word):
        return True
    return False

@profile
def image_score(cv2_im):
    '''Computes a score for the quality of the extracted text
    '''
    print "Reading image..."
    img = Image.fromarray(cv2_im)

    print "Extracting text..."
    final_text = pytesseract.image_to_string(img)

    total = 0
    words = 0
    print "Computing score..."
    final_text = final_text.lower().decode("utf-8").split()
    for word in final_text:
        if is_dictionary_word(word):
            words += 1
        total += 1

    if not total:
        return 0
    # return float(words)/total*100
    if (("nutrition" in final_text) or ("supplement" in final_text) or ("drug" in final_text)):
        return 1
    else:
        return 0

def read_image(filename, is_url=True):
    if is_url:
        req = urllib.urlopen(filename)
        arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
        # src = cv2.imdecode(arr,-1) # 'load it as it is'    else:
        src = cv2.imdecode(arr,cv2.CV_LOAD_IMAGE_GRAYSCALE) # 'load it as grayscale
    else:
        src = cv2.imread(filename, cv2.CV_LOAD_IMAGE_GRAYSCALE)
    return src

def test_extract_text(filenames, is_url=False, debug=False):

    preprocessings = [
        preprocessing1, preprocessing2, preprocessing3,
        preprocessing4, preprocessing5
    ]

    scores = [0 for i in preprocessings]
    max_scores = [0 for i in preprocessings]
    rounds = 0

    params = {
                'debug': [False],
                'gblur1_param1': range(1,11),
                'ablur_param1': range(1,11),
                'ablur_param2': range(1,100,20),
                'dilate_param': range(0,5),
                'erode_param': range(0,5),
                'morph_el': range(1,4),
                'thresh_param1': range(1,25,3),
                'thresh_param2': range(0,50,5),
                'thresh_param3': range(50,200,15),
                'image_size': range(500,4000,800)
            }

    optimal_params = [{} for preprocessing in preprocessings]
    successful_images = [None for preprocessing in preprocessings]


    current_params = {
    'debug': False,
    'gblur1_param1': 5,
    'ablur_param1': 1,
    'ablur_param2': 75,
    'dilate_param': 1,
    'erode_param': 2,
    'morph_el': 1,
    'thresh_param1': 15,
    'thresh_param2': 2,
    'thresh_param3': 170,
    'image_size': 3000
    }
    # param_keys = sorted(params.keys())
    # params to vary
    param_keys = ['thresh_param3', 'image_size']
    param_ranges = map(lambda k: params[k], param_keys)


    # preload the images in memory
    loaded_images = []
    print "Loading images..."
    for filename in filenames:
        src = read_image(filename)
        loaded_images.append(src)


    # just do it for default values of parameters and skip the rest
    for idimg, src in enumerate(loaded_images):
        for idx, preprocessing in enumerate([preprocessings[3]]):
            try:
                src = preprocessing(src)
                score = image_score(src)
                scores[idx] += score
                if score > max_scores[idx]:
                    max_scores[idx] = score
                    successful_images[idx] = filenames[idimg]
                print filenames[idimg]
            except Exception, e:
                print "Exception", e
                pass
                
            print "round", rounds, scores
            rounds += 1
    return

    # do it for all combinations of values of parameters
    # (comment the above block)
    for current_values in itertools.product(*param_ranges):
        print current_values
        for idx, key in enumerate(param_keys):
            current_params[key] = current_values[idx]
        print current_params

    # # skipping the above ^^ ; just with the default parameters:
    # for x in [1]:
        # skip if all are 0
        if not all([False if v is None else True for v in current_params.values()]):
            print "continuing........."
            continue
        for idx, preprocessing in enumerate([preprocessings[3]]):
            score = 0
            for idimg, src in enumerate(loaded_images):
                try:
                    print "Preprocessing image..."
                    img = preprocessing(src, **current_params)
                    print "Computing image score..."
                    curr_score = image_score(img)
                    score += curr_score
                    print curr_score
                    if score > max_scores[idx]:
                        successful_images[idx] = filenames[idimg]
                    
                except Exception, e:
                    print "Exception", e
                    pass

            avg_score = float(score)/len(filenames)
            print "avg score for %d" % idx, avg_score
            scores[idx] += avg_score
            if avg_score > max_scores[idx]:
                max_scores[idx] = avg_score
                optimal_params[idx] = dict(current_params)
                
            print "round", rounds, current_params, scores
            rounds += 1
            print "-----------------------"
            print


    for idx, score in enumerate(scores):
        print "Version %d" % (idx+1)
        print "Average score", float(score)/rounds
        print "Max score", max_scores[idx]
        print "Optimal params", optimal_params[idx]
        print "Most successful image", successful_images[idx]

if __name__=='__main__':
    # test_images = [
    # "http://i5.walmartimages.com/dfw/dce07b8c-a3bb/k2-_2721972a-377f-4843-b951-fe208d776f30.v1.jpg",
    # "http://i5.walmartimages.com/dfw/dce07b8c-fc26/k2-_8a9ed1f0-2492-40a6-ac8c-d711194b3fc4.v1.jpg",
    # "http://i5.walmartimages.com/dfw/dce07b8c-4ea0/k2-_6fac7ed3-4cd9-45bb-8563-3470dbfcd237.v1.jpg",
    # "http://i5.walmartimages.com/dfw/dce07b8c-9dec/k2-_3017fd7b-9975-4e49-8ac7-014db67d23c6.v2.jpg",
    # "http://i5.walmartimages.com/dfw/dce07b8c-3743/k2-_c2121dd9-b52c-43d3-b30a-b5bbc2cde85f.v1.jpg",
    # "http://ecx.images-amazon.com/images/I/519UiiFmggL.jpg",
    # "http://ecx.images-amazon.com/images/I/51oBuOiR%2BFL.jpg",
    # "http://i5.walmartimages.com/dfw/dce07b8c-a773/k2-_2e0d3993-c0ca-4021-9c49-dbbbd69004c2.v1.jpg",
    # "http://ecx.images-amazon.com/images/I/91Det0miFQL._SL1500_.jpg",
    # "http://ecx.images-amazon.com/images/I/61H5FyM21UL.jpg",
    # "http://ecx.images-amazon.com/images/I/81ikCuTaGeL._SL1500_.jpg",
    # "http://ecx.images-amazon.com/images/I/81IvypyzrWL._SL1500_.jpg",
    # ]

    with open("facts_images.csv") as fin:
        test_images = map(lambda l: l.strip(), fin.readlines())

    # test_extract_text(['/tmp/text_image.jpg', '/tmp/text_image2.jpg'])       
    test_extract_text(test_images[25:])       


import cv2
import pytesseract
from PIL import Image
import urllib
import cStringIO # *much* faster than StringIO
import numpy as np
import boto3
import base64
import traceback
import json


def extract_text(filename, is_url=False, debug=False):
    if is_url:
        req = urllib.urlopen(filename)
        arr = np.asarray(bytearray(req.read()), dtype=np.uint8)
        # src = cv2.imdecode(arr,-1) # 'load it as it is'    else:
        src = cv2.imdecode(arr,cv2.CV_LOAD_IMAGE_GRAYSCALE) # 'load it as grayscale
    else:
        src = cv2.imread(filename, cv2.CV_LOAD_IMAGE_GRAYSCALE)

    # smooth
    # src = cv2.GaussianBlur(src,(3,3),0)
    src = cv2.adaptiveBilateralFilter(src,(9,9),75,55)
    if debug:
        cv2.imwrite("/tmp/1blurred.png", src)


    # resize image
    orig_size = src.shape[:2]
    # such that smaller dimension is 500 pixels at least
    normalized_size = max(1500, max(orig_size))
    max_dim_idx = max(enumerate(orig_size), key=lambda l: l[1])[0]
    min_dim_idx = [idx for idx in [0,1] if idx!=max_dim_idx][0]
    new_size = [0,0]
    new_size[min_dim_idx] = normalized_size
    new_size[max_dim_idx] = int(float(orig_size[max_dim_idx]) / orig_size[min_dim_idx] * normalized_size)

    # src = cv2.resize(src=src, dsize=(0,0), dst=src, fx=4, fy=4)
    src = cv2.resize(src=src, dsize=tuple(new_size[::-1]), dst=src, fx=0, fy=0)

    # # smooth
    # # src = cv2.GaussianBlur(src,(5,5),0)
    # src = cv2.adaptiveBilateralFilter(src,(1,1),75,75)
    # cv2.imwrite("/tmp/2blurred2.png", src)
    
    # erode + dilate
    element = cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))
    element2 = cv2.getStructuringElement(cv2.MORPH_CROSS,(3,3))
    # skel = np.zeros(src.shape,np.uint8)

    eroded = cv2.erode(src,element)
    if debug:
        cv2.imwrite("/tmp/3eroded.png", eroded)
    temp = cv2.dilate(eroded,element2)
    if debug:
        cv2.imwrite("/tmp/4dilated.png", temp)
    # temp = cv2.subtract(src,temp)
    # skel = cv2.bitwise_or(skel,temp)
    src = temp

    # black and white
    # src = cv2.adaptiveThreshold(src, 255, adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C, thresholdType=cv2.THRESH_BINARY, blockSize=15, C=2)
    _, src = cv2.threshold(src, 170, 255, cv2.THRESH_BINARY)
    # For large text I think we need the first parameter to be higher
    # src = cv2.adaptiveThreshold(src,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,23,3)
    # _,src = cv2.threshold(src,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    if debug:
        cv2.imwrite("/tmp/5thresh.png", src)
    
    if debug:      
        cv2.imwrite("/tmp/dst.png", src)

    if debug:
        file = urllib.urlopen(filename)
        im = cStringIO.StringIO(file.read()) # constructs a StringIO holding the image
        img = Image.open(im)
        original_text = pytesseract.image_to_string(img)
        print "ORIGINAL", filter(None, original_text.split('\n'))[:3]

        print "-----------------------------------"

    img = Image.fromarray(src)
    final_text = lambda_tesseract(img)
    if final_text is None:
        # fallback to local run
        pytesseract.image_to_string(img)
    if debug:
        print "FINAL", filter(None, final_text.split('\n'))[:30]
    return final_text


def lambda_tesseract(img):
    try:
        buf = cStringIO.StringIO()
        img.save(buf, format='JPEG')
        data = base64.b64encode(buf.getvalue())

        client = boto3.client('lambda', region_name='us-east-1')
        response = client.invoke(
            FunctionName='lambda-tesseract',
            Payload=json.dumps({'image64': data})
        )
    except:
        print 'ERROR: {}'.format(traceback.format_exc())
    else:
        response = json.loads(response.get('Payload').read())
        return response.get('text')


if __name__=='__main__':
    # print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-a3bb/k2-_2721972a-377f-4843-b951-fe208d776f30.v1.jpg", True)
    # print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-fc26/k2-_8a9ed1f0-2492-40a6-ac8c-d711194b3fc4.v1.jpg", True)
    # print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-4ea0/k2-_6fac7ed3-4cd9-45bb-8563-3470dbfcd237.v1.jpg", True)
    # print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-9dec/k2-_3017fd7b-9975-4e49-8ac7-014db67d23c6.v2.jpg", True)
    # print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-3743/k2-_c2121dd9-b52c-43d3-b30a-b5bbc2cde85f.v1.jpg", True)
    # print extract_text("http://ecx.images-amazon.com/images/I/519UiiFmggL.jpg", True)
    # print extract_text("http://ecx.images-amazon.com/images/I/51oBuOiR%2BFL.jpg", True)
    # print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-a773/k2-_2e0d3993-c0ca-4021-9c49-dbbbd69004c2.v1.jpg", True)
    # print extract_text("http://ecx.images-amazon.com/images/I/91Det0miFQL._SL1500_.jpg", True)
    # print extract_text("http://ecx.images-amazon.com/images/I/61H5FyM21UL.jpg", True)
    # print extract_text("http://ecx.images-amazon.com/images/I/81ikCuTaGeL._SL1500_.jpg", True)
    # print extract_text("http://ecx.images-amazon.com/images/I/81IvypyzrWL._SL1500_.jpg", True)
    print extract_text("http://i5.walmartimages.com/dfw/dce07b8c-4d98/k2-_eba6aa70-08fe-4582-ac7a-e981b6b7691d.v1.jpg", True, True)
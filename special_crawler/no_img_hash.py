from flask import Flask, jsonify, request
import json
from PIL import Image
import mmh3 as MurmurHash
import os.path
from io import BytesIO
import requests
from StringIO import StringIO

'''
    Fetches an image, hashes it, and adds/removes it from the desired path

    usage: http://localhost/hash?mode=add&path=no_img_list.json&url=http://tesco.scene7.com/is/image/tesco/436-0793_PI_1000021MN
'''

'''
Examples for Fetching and Hashing:

existing image page = http://www.tesco.com/direct/nvidia-geforce-gt630-graphics-card-2gb-pci-express-x16-displayport/397-4229.prd
url = "http://tesco.scene7.com/is/image/tesco/397-4229_PI_1000021MN"
hash = 176934169

no-image product page = http://www.tesco.com/direct/nvidia-nvs-310-graphics-card-512mb/436-0793.prd
url = "http://tesco.scene7.com/is/image/tesco/436-0793_PI_1000021MN"
hash = 74961158

no-image product page = http://www.tesco.com/direct/nvidia-quadro-410-graphics-card-512mb/538-8755.prd
url = "http://tesco.scene7.com/is/image/tesco/538-8755_PI_1000021MN" 
hash = 74961158
'''

app = Flask(__name__)
mandatory = ['mode', 'url', 'path']

@app.route('/hash', methods=['GET'])
def hasher():
    # this is used to convert an ImmutableMultiDictionary into a regular dictionary. will be left with only one "data" key
    request_arguments = dict(request.args)
        
    if validate_args(request_arguments):
        mode = request_arguments['mode'][0]
        url = request_arguments['url'][0]
        path = request_arguments['path'][0]
                
        no_img_list = []
        
        if os.path.isfile(path):
            f = open(path, 'r')
            s = f.read()
            if len(s) > 1:
                no_img_list = json.loads(s)    
            f.close()
        
        f = open(path, 'w')
        bytes = fetch_bytes(url)
        ihash = str(MurmurHash.hash(bytes))
        
        if mode == "add":
            if ihash not in no_img_list:
                no_img_list.append(ihash)
        elif mode == "remove":
            if ihash in no_img_list:
                no_img_list.remove(ihash)
        
        
        f.write(json.dumps(no_img_list, sort_keys=True,indent=4, separators=(',', ': ')))
        f.flush()
        f.close()
        
        return "done"

#returns True if arguments align exactly with the mandatory arguments
def validate_args(args):
    a = sorted(mandatory)
    b = sorted (args)
    for i in xrange(len(mandatory)):
        if a[i] != b[i]:
            return False
    return True


def fetch_bytes(url, walmart = None):
    agent = 'Mozilla/5.0 (X11; Linux x86_64; rv:24.0) Gecko/20140319 Firefox/24.0 Iceweasel/24.4.0'
    headers ={'User-agent': agent}
    with requests.Session() as s:
        if walmart:
            response = s.get(url, headers=headers, stream=True, timeout=15)
            for chunk in response.iter_content(5000):
                response.close()
                return chunk
        response = s.get(url, headers=headers, timeout=15)
        if response != 'Error' and response.ok:
            img = Image.open(StringIO(response.content))
            b = BytesIO()
            img.save(b, format='png')
            data = b.getvalue()
            return data
        elif response != 'Error' and response.content:
            img = Image.open(StringIO(response.content))
            b = BytesIO()
            img.save(b, format='png')
            data = b.getvalue()
            return data

@app.errorhandler(500)
def handle_internal_error(error):
    response = jsonify({"error" : "Internal server error"})
    response.status_code = 500
    return response


if __name__ == '__main__':
    #app.run('0.0.0.0', port=80, threaded=True)
    app.run('127.0.0.1', port=80, threaded=True)

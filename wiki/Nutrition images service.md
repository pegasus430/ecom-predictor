Nutrition/drug/supplement facts images detection
-------------------------------------------------

This module implements detection and classification of images containing nutrition facts / drug facts / supplement facts.

e.g. http://ecx.images-amazon.com/images/I/519UiiFmggL.jpg

The code can be found in `tmtext/nutrition_info_images`

- `tmtext/nutrition_info_images/classify_text_images.py` contains the actual classifier and functions for deciding if an image is a text (nutrition/drug/supplement) image or not
- `tmtext/nutrition_info_images/serialized_classifier` contains the serialized trained classifier that will be loaded to be used to make predictions (classify new images)
- `tmtext/nutrition_info_service.py` contains the REST service and web interface for detecting nutrition/drug/supplement images
- `tmtext/nutrition_info_images/nutrition info` and `tmtext/nutrition_info_images/generate_nutrition_from_text.py` contain crawlers and tools used in building this classifier

REST service
--------------

__Location__
==============

The service is currently deployed on this server:

    IP: imageprocess.contentanalyticsinc.com
    Port: 80

__Resources__
==============

## GET `/nutrition_image?image=<image_url>`

__Request parameters__
======================

- `image` (mandatory) - the image URL of the input image. It is recommended that the URL is percent-encoded, especially if it contains `&` characters.

Supports any number of `image` parameters and all their values will be handled in the request.

**Important!** Request fails and service stops if input URL is not an image URL.

__Responses__
=============

The service returns a JSON object containing the prediction for each image:
keys will be the input image URLs and values will be a string representing the type of the image:

- "nutrition_facts" - if image is a nutrition facts image
- "drug_facts" - if image is a drug facts image
- "supplement_facts" - if image is a supplement facts image
- "unknown" - if image is likely to be a nutrition/drug/supplement facts image, but its exact type could not be determined
- None - if image is not a nutrition/drug/supplement facts image at all

Status codes:

- `200` - request was successful
- `404` - route was not found
- `400` - invalid usage (usually bad parameters)
- `500` - internal server error

## Errors

In case of any error (400/404/500), the service will return a JSON response with the key `"error"` and the value a relevant message.


__Usage and response example__
===============================

Successful response:

    $ curl http://54.172.69.67/nutrition_image?image=http://i5.walmartimages.com/dfw/dce07b8c-289f/k2-_0820016c-d614-48e6-abda-251e47ca69a4.v3.jpg&image=http://i5.walmartimages.com/dfw/dce07b8c-7645/k2-_a6be6636-7b2e-4552-ae19-1eb9f0ca8091.v1.jpg&image=http://i5.walmartimages.com/dfw/dce07b8c-a773/k2-_2e0d3993-c0ca-4021-9c49-dbbbd69004c2.v1.jpg

    {
      "http://i5.walmartimages.com/dfw/dce07b8c-289f/k2-_0820016c-d614-48e6-abda-251e47ca69a4.v3.jpg": null, 
      "http://i5.walmartimages.com/dfw/dce07b8c-7645/k2-_a6be6636-7b2e-4552-ae19-1eb9f0ca8091.v1.jpg": null,
      "http://i5.walmartimages.com/dfw/dce07b8c-a773/k2-_2e0d3993-c0ca-4021-9c49-dbbbd69004c2.v1.jpg": "nutrition_facts"
    }

Web user interface
-------------------

The same service also offers a user interface, at the following resource:

## GET `/nutrition_image_UI`

Server setup and deployment
-----------------------------

The service is deployed using **uwsgi + nginx** web server.

## Dependencies

Debian packages:

  - python-virtualenv
  - python-dev
  - libatlas-base-dev
  - gfortran
  - libfreetype6-dev
  - python-opencv
  - libjpeg-dev
  - tesseract-ocr
  - nginx
  - uwsgi
  - uwsgi-plugin-python

Python packages: 

  - flask
  - numpy
  - scipy
  - scikit-learn
  - matplotlib
  - pytesseract
  - pillow
  - fuzzywuzzy
  - boto3

Step-by-step installation:

  - clone repo from git:
```
#!bash

git clone https://bitbucket.org/dfeinleib/tmtext.git
```
  - install packages
```
#!bash

sudo apt-get update
sudo apt-get install -y python-virtualenv python-dev libatlas-base-dev gfortran libfreetype6-dev python-opencv libjpeg-dev tesseract-ocr nginx uwsgi uwsgi-plugin-python

sudo ln -s /usr/include/freetype2/ft2build.h /usr/include/
```
  - create and activate virtual environment
```
#!bash

virtualenv tmtextenv
source tmtextenv/bin/activate
```
  - install Python libraries
```
#!bash

pip install flask numpy scipy scikit-learn matplotlib pytesseract pillow fuzzywuzzy boto3

ln -s /usr/lib/python2.7/dist-packages/cv2.so /home/ubuntu/tmtextenv/lib/python2.7/site-packages/cv2.so
ln -s /usr/lib/python2.7/dist-packages/cv.py /home/ubuntu/tmtextenv/lib/python2.7/site-packages/cv.py

```
  - setup Nginx
```
#!bash

sudo rm /etc/nginx/sites-enabled/default
sudo tee /etc/nginx/sites-available/nutrition_images <<EOF
server {
    listen      80 default_server;
    server_name _;
    charset     utf-8;
    client_max_body_size 75M;

    location / { try_files \$uri @flaskapp; }
    location @flaskapp {
        include uwsgi_params;
        uwsgi_pass 127.0.0.1:8001;
        uwsgi_read_timeout 120s;
        uwsgi_send_timeout 120s;
    }
}

EOF

sudo ln -s /etc/nginx/sites-available/nutrition_images /etc/nginx/sites-enabled/nutrition_images
sudo service nginx restart
```
  - setup Uwsgi
```
#!bash

sudo tee /etc/uwsgi/apps-available/nutrition_images.ini <<EOF
[uwsgi]
socket = 127.0.0.1:8001
chmod-socket = 644
chdir = /home/ubuntu/tmtext/nutrition_info_images
wsgi-file = /home/ubuntu/tmtext/nutrition_info_images/nutrition_images_service.py
virtualenv = /home/ubuntu/tmtextenv
home = /home/ubuntu/tmtextenv
callable = app
; master = true
; www-data uid/gid
uid = www-data
gid = www-data
buffer-size=32768
die-on-term = true
processes = 4
threads = 2
logger = file:/var/log/flask-uwsgi/nutrition_images.log
plugins = logfile, python

EOF

sudo ln -s /etc/uwsgi/apps-available/nutrition_images.ini /etc/uwsgi/apps-enabled/nutrition_images.ini

sudo mkdir /var/log/flask-uwsgi/
sudo chgrp www-data /var/log/flask-uwsgi
sudo chmod g+rwxs /var/log/flask-uwsgi

sudo service uwsgi restart
```

Replace `ubuntu` on your user if it is necessary

__AWS Lambda__
===============
Put Tesseract OCR to Lambda function to increase performance. Text extraction falls back to local run if Lambda function failed.

Prepare deployment package
---------------------------
```
#!bash

sudo yum -y groupinstall "Development Tools"
sudo yum -y install libtool
sudo yum -y install libjpeg-devel libpng-devel libtiff-devel zlib-devel

curl http://www.leptonica.com/source/leptonica-1.74.4.tar.gz | tar xzv
cd leptonica-1.74.4 && ./configure && make && sudo make -j 4 install && cd ..

curl -L https://github.com/tesseract-ocr/tesseract/archive/3.05.tar.gz | tar xzv
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig
cd tesseract-3.05/ && ./autogen.sh && ./configure && make && sudo make -j 4 install && cd ..

mkdir lambda-tesseract
mkdir lambda-tesseract/lib
cp /usr/local/lib/{libtesseract.so.3,liblept.so.5} lambda-tesseract/lib/
cp /lib64/libz.so.1 lambda-tesseract/lib/
cp /usr/lib64/{libpng12.so.0,libjpeg.so.62,libtiff.so.5,libjbig.so.2.0} lambda-tesseract/lib/
cp /usr/local/bin/tesseract lambda-tesseract/

mkdir lambda-tesseract/tessdata
curl -L https://github.com/tesseract-ocr/tessdata/archive/3.04.00.tar.gz | tar xzv
cp tessdata-3.04.00/{eng.*,osd.traineddata} lambda-tesseract/tessdata/
cp tesseract-3.05/tessdata/eng.* lambda-tesseract/tessdata/
cp tesseract-3.05/tessdata/pdf.ttf lambda-tesseract/tessdata/
mkdir lambda-tesseract/tessdata/configs
cp tesseract-3.05/tessdata/configs/pdf lambda-tesseract/tessdata/configs

virtualenv ~/tfenv
source ~/tfenv/bin/activate
pip install pytesseract
cp -r ~/tfenv/lib/python2.7/site-packages/* lambda-tesseract/
cp -r ~/tfenv/lib64/python2.7/site-packages/* lambda-tesseract/

tee lambda-tesseract/lambda_function.py <<EOF
import pytesseract
import PIL.Image
import io
import os
from base64 import b64decode


LAMBDA_TASK_ROOT = os.environ.get('LAMBDA_TASK_ROOT', os.path.dirname(os.path.abspath(__file__)))
os.environ["PATH"] += os.pathsep + LAMBDA_TASK_ROOT

def lambda_handler(event, context):
  binary = b64decode(event['image64'])
  image = PIL.Image.open(io.BytesIO(binary))
  text = pytesseract.image_to_string(image)
  return {'text' : text}

EOF

cd lambda-tesseract
zip -r ~/lambda-tesseract.zip ./* --exclude *.pyc
```

Create Lambda function
-----------------------
Ticket https://contentanalytics.atlassian.net/browse/IT-30682

Region: us-east-1

Name: lambda-tesseract

Code entry type: Upload deployment package

Runtime: Python 2.7

Handler: lambda_function.lambda_handler

Environment variables: TESSDATA_PREFIX with empty Value

Basic settings: Memory=1024MB, Timeout=1 min
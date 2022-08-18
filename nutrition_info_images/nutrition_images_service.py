from flask import Flask, request, jsonify, render_template
from classify_text_images import classifier_predict_one, load_classifier, predict_textimage_type
app = Flask(__name__)

import datetime
import logging
from logging import StreamHandler
import json
from urllib2 import HTTPError

# add logger
# using StreamHandler ensures that the log is sent to stderr to be picked up by uwsgi log
fh = StreamHandler()
fh.setLevel(logging.DEBUG)
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(fh)

image_classifier = load_classifier()
jet_image_classifier = load_classifier(path="serialized_classifier/jet_nutrition_image_classifier.pkl")

class CustomError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


@app.route('/nutrition_image_results', methods=['GET'])
def results():
    # example request: 
    # http://127.0.0.1:5000/is_nutrition_image?image=http://i5.walmartimages.com/dfw/dce07b8c-bf9c/k2-_f6770975-97a9-474c-a3c8-8edc3a4a14e1.v1.jpg&image=http://i5.walmartimages.com/dfw/dce07b8c-9417/k2-_6275bca7-da12-4925-9afd-048eea86da73.v1.jpg
    request_arguments = dict(request.args)
    image_urls = request_arguments['image'][0].split()
    return render_template('results_template.html', \
        results={image : get_image_type(image) for image in image_urls})

@app.route('/nutrition_image_UI', methods=['GET'])
def nutrition_image_UI():
    return render_template('input_template.html')

@app.route('/nutrition_image', methods=['GET'])
def is_nutrition_image():
    request_arguments = dict(request.args)
    validate_args(request_arguments)
    image_urls = request_arguments['image']
    try:
        results = {image : get_image_type(image) for image in image_urls}
    except HTTPError:
        raise CustomError("Error retrieving image")
    return jsonify(results)

def get_image_type(image_url):
    '''Predicts if image is a text image or not (nutrition/drug/supplement)
    and which type (nutrition/drug/supplement facts)
    Returns 1 of 5 values:
    nutrition_facts, drug_facts, supplement_facts, unknown (if text image but type unknown)
    and None (if not text image at all)
    '''

    if classifier_predict_one(image_url, jet_image_classifier) != 0:
        return 'nutrition_facts'

    # not a text image at all
    if classifier_predict_one(image_url, image_classifier) == 0:
        return None

    image_type = predict_textimage_type(image_url)
    if not image_type:
        return "unknown"

    return image_type

def validate_args(arguments):
    # normalize all arguments to str
    argument_keys = map(lambda s: str(s), arguments.keys())

    mandatory_keys = ['image']

    # If missing any of the needed arguments, throw exception
    for argument in mandatory_keys:
        if argument not in argument_keys:
            raise CustomError("Invalid usage: missing GET parameter: " + argument)

# post request logger
@app.after_request
def post_request_logging(response):

    app.logger.info(json.dumps({
        "date" : datetime.datetime.today().ctime(),
        "remote_addr" : request.remote_addr,
        "request_method" : request.method,
        "request_url" : request.url,
        "response_status_code" : str(response.status_code),
        "request_headers" : ', '.join([': '.join(x) for x in request.headers])
        })
    )

    return response

@app.errorhandler(CustomError)
def handle_custom_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.errorhandler(500)
def handle_internal_error(error):
    response = jsonify({"error" : "Internal server error"})
    response.status_code = 500
    return response

@app.errorhandler(404)
def handle_not_found(error):
    response = jsonify({"error" : "Not found"})
    response.status_code = 404
    return response

if __name__ == '__main__':
    app.run('0.0.0.0', port=8080)

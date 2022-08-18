import requests
import traceback
import re

from flask import url_for
from urlparse import urlparse


# load product data
def load_product(url):
    try:
        response = requests.get(url_for('get_data', _external=True), params={'url': url})
        response.raise_for_status()

        return response.json()
    except:
        print traceback.format_exc()


# returns a list containing all Image URLs found in a webpage
def get_color_url(product, color):
    swatches = product.get('page_attributes', {}).get('swatches')

    if swatches:
        for entry in swatches:
            if entry.get('color') == color and entry.get('hero_image'):
                return entry.get('hero_image')[0]


# this returns a list of the images found in the left bar (the ALT images)
def get_image_urls(product):
    image_urls = product.get('page_attributes', {}).get('image_urls')

    if image_urls:
        result = []

        for image_url in image_urls:
            image_url_parts = urlparse(image_url)
            image_id = image_url_parts.path.split('/')[-1].split('.')[0]

            if re.search(r'M$', image_id, re.I):
                result.append({'id': image_id, 'url': image_url})

        return map(lambda x: x['url'], filter_result(result))


# WE STILL NEED SOME WAY TO FLITER OUT THE URLS
# WILL PROBABLY WANT TO FILTER BY LIKENESS OF ID TAG
def filter_result(result):
    if len(result) <= 5:
        return result

    filtered = []
    seen = set()

    for image in result:
        sub_id = image.get('id')[:-4]

        if sub_id in seen:
            filtered.append(image)
        else:
            seen.add(sub_id)

    return filtered


def get_video(product):
    return product.get('page_attributes', {}).get('video_count')


def get_size_chart(product):
    return product.get('page_attributes', {}).get('size_chart')


def get_fit_guide(product):
    return product.get('page_attributes', {}).get('fit_guide')

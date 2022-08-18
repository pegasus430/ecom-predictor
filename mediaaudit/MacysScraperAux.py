import traceback
import requests

from flask import url_for


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
def get_image_urls(product, color):
    swatches = product.get('page_attributes', {}).get('swatches')

    if swatches:
        for entry in swatches:
            if entry.get('color') == color and entry.get('hero_image'):
                return entry.get('hero_image')


def get_video(product):
    return product.get('page_attributes', {}).get('video_count')


def get_size_chart(product):
    return product.get('page_attributes', {}).get('size_chart')

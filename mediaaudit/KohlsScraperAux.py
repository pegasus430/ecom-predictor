import requests
import traceback

from flask import url_for


# load product data
def load_product(url):
    try:
        response = requests.get(url_for('get_data', _external=True), params={'url': url})
        response.raise_for_status()
        return response.json()
    except:
        print traceback.format_exc()


def check_state(product):
    if not product:
        return False
    state = product.get('status')
    return state and state == 'success'


# returns a list containing all Image URLs found in a webpage
def get_color_urls(product):
    color_urls = set()

    image_urls = product.get('page_attributes', {}).get('image_urls')
    if image_urls:
        for image_url in image_urls:
            if 'ALT' not in image_url:
                color_urls.add(image_url)

    meta_tags = product.get('page_attributes', {}).get('meta_tags')
    if meta_tags:
        for meta_tag in meta_tags:
            if len(meta_tag) > 1 and meta_tag[0] == 'image':
                color_urls.add(meta_tag[1])
    # put same id firstly
    ordered_list = sorted(list(color_urls), key=lambda x: (product['product_id'] not in x))
    return ordered_list


# this returns a list of the images found in the left bar (the ALT images)
def get_image_urls(product):
    image_urls = product.get('page_attributes', {}).get('image_urls')

    if image_urls:
        result = []
        for image_url in image_urls:
            if 'ALT' in image_url:
                result.append(image_url)
        return result


def get_video(product):
    return product.get('page_attributes', {}).get('video_count')


def get_size_chart(product):
    return product.get('page_attributes', {}).get('size_chart')

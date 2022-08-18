import requests
from requests.auth import HTTPBasicAuth

COMPARE_URL = 'http://mediacompare.contentanalyticsinc.com/compare'


# Calls Comparison API #
def call_endpoint(url1, url2):
    response = requests.get(
        COMPARE_URL,
        params={
            'media_type': 'image',
            'compare_method': 'local',
            'first_url': url1,
            'second_url': url2,
        },
        auth=HTTPBasicAuth('user', 'tE3OqHDZPk')
    ).json()

    if response.get('error'):
        raise Exception(response.get('message'))

    return response.get('result')

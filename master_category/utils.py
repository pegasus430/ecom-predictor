import requests
import traceback


GOOGLE_MC_APPROVED_BRANDS_API_URL = (
    '{srv}/api/customers/{customer_id}/approved-brands?api_key={api_key}'
)

_mc_api_keys = {}


def get_mc_api_key(server):
    if server not in _mc_api_keys:
        print('Requesting API key for server {}'.format(server))
        api_url = '{server}/api/token?username=api@cai-api.com&password=jEua6jLQFRjq8Eja'.format(server=server)
        response = requests.get(api_url)
        response.raise_for_status()
        data = response.json()
        _mc_api_keys[server] = data['api_key']
    return _mc_api_keys[server]


def get_google_mc_approved_brands(server, customer_id):
    try:
        url = GOOGLE_MC_APPROVED_BRANDS_API_URL.format(
            srv=server, customer_id=customer_id, api_key=get_mc_api_key(server))
        response = requests.get(url)
        if response.status_code != 200:
            print(
                'Unexpected response from {}: response code {}, content: {}'.format(
                    url,
                    response.status_code,
                    response.content
                )
            )
            raise Exception('Unexpected response code from MC API.')
        approved_brands_list = response.json()
        approved_brands_dict = {}
        for approved_brand in approved_brands_list:
            brand = approved_brand.get('brand')
            alias = approved_brand.get('brand_alias')
            approved_brands_dict[brand] = alias

        return approved_brands_dict
    except:
        print(traceback.format_exc())
    return None

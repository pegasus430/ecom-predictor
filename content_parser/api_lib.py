import json
import time
import requests
import traceback
from urllib import quote

ENDPOINT = 'https://{0}.contentanalyticsinc.com/api/{1}'
CREDENTIALS = 'username=api@cai-api.com&password=jEua6jLQFRjq8Eja'
HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

def _old_credentials(server_name):
    passwd = server_name[0].upper() + server_name.lower()[1:] + '.2014'
    return 'username=bayclimber@gmail.com&password={}'.format(passwd)

def get_api_key_and_token(filename, customer, server_name):
    print 'requesting api key and token for', filename
    for _ in range(3):
        try:
            # Try getting api key
            response = requests.get(
                ENDPOINT.format(server_name, 'token') + '?' + CREDENTIALS,
            )
            print response.content

            if response.json().get('api_key'):
                api_key = response.json()['api_key']

                response = requests.post(
                    ENDPOINT.format(server_name, 'import'),
                    data='api_key={0}&customer={1}&file_name={2}'.format(api_key, customer, filename),
                    headers=HEADERS
                )
                print response.content
                token = response.json()['token']
                return api_key, token

            response = requests.post(
                ENDPOINT.format(server_name, 'import'),
                data=_old_credentials(server_name) + '&customer={0}&file_name={1}'.format(customer, filename),
                headers=HEADERS
            )
            print response.content
            token = response.json()['token']
            return None, token
        except:
            print traceback.format_exc()
            time.sleep(10)


def report_status(api_key, token, status, server_name):
    print 'reporting status for', token, status

    for _ in range(3):
        try:
            data='token={0}&status={1}'.format(token, str(status))
            if api_key:
                data += '&api_key={}'.format(api_key)
            else:
                data += '&' + _old_credentials(server_name)

            requests.put(
                ENDPOINT.format(server_name, 'import'),
                data=data,
                headers=HEADERS
            )
            return
        except:
            print traceback.format_exc()
            time.sleep(10)


def send_json(api_key, token, products_json, server_name):
    print 'sending json'

    try:
        ugly_string = ''

        i = 0

        for product in products_json:
            product_no = 'products[%s]' % str(i)

            for key in product:
                ugly_string += '&'

                if type(product[key]) is dict:
                    first = True

                    for key2 in product[key]:
                        value = product[key][key2]
                        value = value if isinstance(value, int) else quote(product[key][key2])
                        s = '[%s][%s]=%s' % (key, key2, value)
                        if not first:
                            ugly_string += '&'
                        ugly_string += product_no + s
                        first = False

                else:
                    if type(product[key]) is list:
                        s = '[%s]=%s' % (key, quote(json.dumps(product[key])))
                    else:
                        s = '[%s]=%s' % (key, quote(product[key].encode('utf8')) if product[key] else None)
                    ugly_string += product_no + s
            i += 1

        for _ in range(3):
            try:
                data = 'token={}'.format(token)
                if api_key:
                    data += '&api_key={}'.format(api_key)
                else:
                    data += '&' + _old_credentials(server_name)

                response = requests.put(
                    ENDPOINT.format(server_name, 'import/products'),
                    data=data + ugly_string,
                    headers=HEADERS)

                print 'SENT JSON AND GOT', response.content
                return response.json()['token'], response.json()
            except:
                print traceback.format_exc()
                time.sleep(10)
    except:
        print traceback.format_exc()

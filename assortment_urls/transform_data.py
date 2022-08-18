import sys
import json


if __name__ == '__main__':
    input_fname = sys.argv[1]

    input_urls = open(input_fname, 'r').readlines()
    input_urls = [u.strip() for u in input_urls if u.strip()]

    j = open(input_fname, 'r').read()
    j = json.loads(j)

    _current_input_url = input_urls[0]
    for assort_url in j:
        for key, value in assort_url.items():
            _url = value.keys()[0]
            _prod_urls = value.values()[0]
            if not _url.startswith(_current_input_url):
                print _url
                _current_input_url = _url
            for _prod_url in _prod_urls:
                print ';'+_prod_url
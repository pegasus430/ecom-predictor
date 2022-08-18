#
# This script shows properties for only out-of-stock and unavailable Variants
#

import os
import sys
import json

from colorama import Fore, Back, init as colorama_init


def _process_file(fname):
    sep = ' --> '
    colorama_init()
    print Back.BLACK

    j_content = [json.loads(line) for line in open(fname, 'r').readlines()
                 if line.strip()]
    for i, j_line in enumerate(j_content):
        if not 'url' in j_line:
            print Fore.RED, 'No URL on line', i+1, Fore.RESET
            print
            continue
        url = j_line['url']
        if not 'variants' in j_line:
            print Fore.GREEN, url, Fore.BLUE, sep, Fore.ORANGE, 'no variants found', Fore.RESET
            print
            continue
        _url_printed = False
        for v in j_line['variants']:
            _oos = v.get('in_stock', None) == False
            _unavailable = v.get('unavailable', None) == True
            if _oos:
                if not _url_printed:
                    print Fore.GREEN, url, Fore.RESET
                    _url_printed = True
                print ' '*4, Fore.BLUE, sep, Fore.WHITE, v['properties'], sep, Fore.YELLOW, 'OOS'
            if _unavailable:
                if not _url_printed:
                    print Fore.GREEN, url, Fore.RESET
                    _url_printed = True
                print ' '*4, Fore.BLUE, sep, Fore.WHITE, v['properties'], sep, Fore.YELLOW, 'UNAVAILABLE'
        print
    print Back.RESET


if __name__ == '__main__':
    _process_file(sys.argv[1])
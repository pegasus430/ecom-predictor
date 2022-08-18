#!/usr/bin/env python2
# vim:fileencoding=UTF-8

from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function
from future_builtins import *

import json
import bz2


def is_plain_json_list(fname):
    with open(fname, 'r') as fh:
        cont = fh.read(1024)
    cont = cont.strip()
    if not cont:
        return True
    return cont[0] == '{'


def unbzip(f1, f2):
    try:
        f = bz2.BZ2File(f1)
        cont = f.read()
    except:
        return False
    f.close()
    with open(f2, 'wb') as fh:
        fh.write(cont)
    return True


def fix_double_bzip_in_file(fname):
    if not is_plain_json_list(fname):
        result1 = unbzip(fname, fname)
        while result1:
            result1 = unbzip(fname, fname)


def parse_arguments():
    import argparse
    parser = argparse.ArgumentParser(
        description='Merge spider outputs to populate best seller ranking as an'
                    ' additional field.',
        version="%(prog)s 0.1")
    parser.add_argument('ranking', help="a JSONLines file.")
    parser.add_argument('best_seller_ranking',
                        help="a JSONLines file ranked by best seller.")

    return parser.parse_args()


def main():
    args = parse_arguments()

    # Load best seller ranked products.
    best_seller_rankings = {}
    if not is_plain_json_list(args.best_seller_ranking):
        fix_double_bzip_in_file(args.best_seller_ranking)
    best_seller_f = open(args.best_seller_ranking)
    for line in best_seller_f:
        try:
            product = json.loads(line)
        except Exception as e:
            with open('/tmp/_line', 'wb') as fh:
                fh.write(str(line))
        url = product['url']
        ranking = product['ranking']
        if url in best_seller_rankings \
                and ranking != best_seller_rankings[url]:
            print("Found product with more than one best sellers ranking."
                  " '%s' has %d and %d. Using lowest."
                  % (url, best_seller_rankings[url], ranking),
                  file=sys.stderr)
            ranking = min(best_seller_rankings[url], ranking)
        best_seller_rankings[url] = ranking

    # Update first data set with best seller's ranking.
    if not is_plain_json_list(args.ranking):
        fix_double_bzip_in_file(args.ranking)
    ranking_f = open(args.ranking)
    for line in ranking_f:
        try:
            product = json.loads(line)
        except Exception as e:
            with open('/tmp/_bs_error_products.log', 'a') as fh:
                try:
                    fh.write(line + '\n\n')
                except Exception as e:
                    pass
            continue
        product['best_seller_ranking'] = best_seller_rankings.get(
            product['url'])

        json.dump(product, sys.stdout, sort_keys=True)
        sys.stdout.write(b'\n')

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

#!/usr/bin/env python2
# vim:fileencoding=UTF-8

from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function
from future_builtins import *

import json

from product_ranking.pipelines import AddSearchTermInTitleFields


def parse_arguments():
    import argparse
    parser = argparse.ArgumentParser(
        description="Perform post-processing for a product-ranking's"
                    " spider output.",
        version="%(prog)s 0.1")

    return parser.parse_args()


def main():
    _ = parse_arguments()

    for line in sys.stdin:
        product = json.loads(line)

        product = AddSearchTermInTitleFields.process_item(product, None)

        json.dump(product, sys.stdout)
        sys.stdout.write(b'\n')
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

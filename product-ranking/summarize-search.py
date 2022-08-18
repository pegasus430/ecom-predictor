#!/usr/bin/env python2
# vim:fileencoding=UTF-8

from __future__ import division, absolute_import, unicode_literals
from __future__ import print_function
from future_builtins import *

from functools import partial
from itertools import chain
from collections import defaultdict
import csv
import json
import sys


def parse_arguments(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Summarize search data.',
                                     version="%(prog)s 0.1")
    #"usage: %prog [options] output-file data-file [data-file ...]",
    parser.add_argument('--filter', help="filter on <property>=<value>")
    parser.add_argument('output', help="the CSV output file.")
    parser.add_argument('inputs', nargs='+', help="the JSON line input files.")

    return parser.parse_args(argv)


def main(argv=None):
    """main([argv]):int

    Optionally receives the argument vector. If it is not provided,
    sys.argv is used.
    Returns the return status code.
    """
    args = parse_arguments(argv)

    sentinel = ' sentinel '
    if args.filter:
        prop, value = args.filter.split('=')
        value = value.lower()
    else:
        prop = None
        value = sentinel

    dol = partial(defaultdict, list)  # defaultdict of list.
    d2ol = partial(defaultdict, dol)  # defaultdict of defaultdict of list.
    d3ol = partial(defaultdict, d2ol)  # ...
    data = d3ol()
    for jl in chain.from_iterable(map(open, args.inputs)):
        rec = json.loads(jl)
        if rec.get(prop, sentinel).lower() == value:
            data[
                rec['site']                     # First level, Sites.
            ][
                rec['search_term']              # Second level, search terms.
            ][
                rec.get('brand', '').lower()    # Third level, brands.
            ].append(rec)                       # Last, a list with the prods.

    writer = csv.writer(
        sys.stdout if args.output == '-' else open(args.output, 'w'))
    writer.writerow(['site', 'search term', 'brand', 'total results',
                     'rankings', 'on first page'])
    for site, search_terms in data.items():
        for st, brands in search_terms.items():
            for brand, recs in brands.items():
                page_size = recs[0]['results_per_page']
                rankings = sorted(r['ranking'] for r in recs)
                on_first_page = sum(1 for r in rankings if r <= page_size)
                writer.writerow(
                    (site,
                     st,
                     brand.capitalize(),
                     recs[0]['total_matches'],
                     rankings,
                     "%d/%d" % (on_first_page, page_size),
                     )
                )

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

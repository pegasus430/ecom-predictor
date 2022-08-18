import csv
import os.path

import pytest

from spiders_shared_code import canonicalize_url


def load_data(site):
    base, _ = os.path.splitext(__file__)
    with open('{}.{}.data.csv'.format(base, site)) as data:
        return [tuple(row) for row in csv.reader(data)]


@pytest.mark.parametrize('input_,expected', load_data('jcpenney'))
def test_jcpenney__product(input_, expected):
    assert canonicalize_url.jcpenney(input_) == expected


@pytest.mark.parametrize('input_,expected', load_data('samsclub'))
def test_samsclub__product(input_, expected):
    assert canonicalize_url.samsclub(input_) == expected


@pytest.mark.parametrize('input_,expected', load_data('johnlewis'))
def test_johnlewis__product(input_, expected):
    assert canonicalize_url.johnlewis(input_) == expected

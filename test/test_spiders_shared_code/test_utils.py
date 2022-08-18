import copy

import mock
import pytest

from spiders_shared_code import utils


TEST_INPUT = [
    [
        'walmart.com',
        [
            ['example\.com', {'cache': {'max-age': 3600}}],
            ['walmart\.com', {'cache': {'max-age': 3000}}],
            ['.+', {'cache': {'host': 'cache.com', 'port': 3000}}]
        ],
        {'cache': {
            'max-age': 3000,
            'host': 'cache.com',
            'port': 3000
        }}
    ], [
        'walmart.com:8080',
        [
            ['example\.com', {'cache': {'max-age': 3600}}],
            ['walmart\.com', {'cache': {'max-age': 3000}}],
            ['.+', {'cache': {'host': 'cache.com', 'port': 3000}}]
        ],
        {'cache': {
            'max-age': 3000,
            'host': 'cache.com',
            'port': 3000
        }}
    ], [
        'images.walmart.com:8080',
        [
            ['example\.com', {'cache': {'max-age': 3600}}],
            ['walmart\.com', {'cache': {'max-age': 3000}}],
            ['.+', {'cache': {'host': 'cache.com', 'port': 3000}}]
        ],
        {'cache': {
            'host': 'cache.com',
            'port': 3000
        }}
    ]
]


@pytest.mark.parametrize('domain,data,expected', TEST_INPUT)
def test_compile_settings__expected(domain, data, expected):
    assert utils.compile_settings(data, domain=domain) == expected


@mock.patch('__builtin__.reversed')
def test_compile_settings__none_raw_settings(mocked_reversed):
    assert utils.compile_settings(None, domain=object()) is None
    assert not mocked_reversed.called


@mock.patch('__builtin__.reversed')
def test_compile_settings__none_domain(mocked_reversed):
    assert utils.compile_settings(object(), domain=None) is None
    assert not mocked_reversed.called


TEST_INPUT = [
    [
        [{'cache': {'max-age': 3600}}, {'cache': {'port': 3000}}],
        {'cache': {'max-age': 3600, 'port': 3000}}
    ], [
        [{'cache': {'max-age': 3600, 'port': 8000}},
         {'cache': {'port': 3000}}],
        {'cache': {'max-age': 3600, 'port': 3000}}],
    [
        [{'cache': {'max-age': 3600, 'hostport': ['cache.com', 3000]}},
         {'cache': {'port': 3000, 'hostport': ['cache.com', 8000]}}],
        {'cache': {'max-age': 3600, 'port': 3000, 'hostport': ['cache.com', 8000]}}
     ], [
         [{'cache': {'when': {'date': '26', 'time': '10pm'}}},
          {'cache': {'when': {'date': '30'}}}],
         {'cache': {'when': {'date': '30', 'time': '10pm'}}}
     ]
]


@pytest.mark.parametrize('data,_', TEST_INPUT)
def test_merge_dict__original_intact(data, _):
    original = copy.deepcopy(data)
    utils.merge_dict(*data)
    assert original == data


@pytest.mark.parametrize('data,expected', TEST_INPUT)
def test_merge_dict__expected(data, expected):
    assert utils.merge_dict(*data) == expected

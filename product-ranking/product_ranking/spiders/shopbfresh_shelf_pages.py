# -*- coding: utf-8 -*-

import json

import re
from product_ranking.spiders.shopbfresh import ShopBfreshProductsSpider
from scrapy.http import Request
from scrapy.log import ERROR


class ShopBfreshShelfPagesSpider(ShopBfreshProductsSpider):
    name = 'shopbfresh_shelf_urls_products'

    shelf_formdata = \
        {
            "meta": {},
            "request": [
                {
                    "args": {
                        "store_id": "00034100",
                        "slugs": [],
                        "facets": [],
                        "sort": "",
                        "extended": True
                    },
                    "v": "0.1",
                    "type": "store.products",
                    "id": "catalog",
                    "offset": 1,
                    "join": [
                        {
                            "apply_as": "facets_base",
                            "on": [
                                "slug", "slug"
                            ],
                            "request": {
                                "v": "0.1",
                                "type": "store.facets",
                                "args": {
                                    "store_id": "$request.[-2].args.store_id",
                                    "slug": "$request.[-2].args.slugs|first",
                                    "basic_facets": []
                                }
                            }
                        },
                        {
                            "apply_as": "category_tree",
                            "on": ["slug", "requested_slug"],
                            "request": {
                                "v": "0.1",

                                "type": "store.department_tree",
                                "args": {
                                    "store_id": "$request.[-2].args.store_id",
                                    "slug": "$request.[-2].args.slugs|first"
                                }
                            }
                        }
                    ]
                }
            ]
        }

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.current_page = 1
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(ShopBfreshShelfPagesSpider, self).__init__(*args, **kwargs)

    @staticmethod
    def _get_category(url):
        categories = re.search(r'https://shop.bfresh.com/en/(.+)', url)
        if categories:
            return [x for x in categories.group(1).split('/') if x.strip()]
        return []

    def start_requests(self):
        categories = self._get_category(self.product_url)
        if categories:
            self.shelf_formdata['request'][0]['args']['slugs'] = categories
            yield Request(self.QUERY_URL,
                          method='POST',
                          headers=self.HEADERS,
                          body=json.dumps(self.shelf_formdata),
                          meta={'search_term': "", 'remaining': self.quantity, 'formdata': self.shelf_formdata}
                          )
        else:
            self.log("Unable to extract categories from product url, initial request's launching failed", ERROR)

# -*- coding: utf-8 -*-

import re

from .superamamx import SuperamaMxProductSpider
from scrapy.http import Request


class SuperamaMxShelfPagesSpider(SuperamaMxProductSpider):
    name = 'superamamx_shelf_urls_products'
    allowed_domains = ["www.superama.com.mx"]

    CATEGORY_URL = 'https://www.superama.com.mx/buscador/resultado?busqueda=&departamento={department}&familia={family}&linea={line}'

    def __init__(self, *args, **kwargs):
        kwargs.pop('quantity', None)
        self.num_pages = int(kwargs.pop('num_pages', '1'))
        super(SuperamaMxShelfPagesSpider, self).__init__(*args, **kwargs)

    def start_requests(self):
        category = re.findall('catalogo/(.*?)$', self.product_url)
        if category:
            category = category[0].split('/')
            if len(category) == 3:
                url = self.CATEGORY_URL.format(department=category[0], family=category[1], line=category[2])
                yield Request(url=url,
                              meta={'search_term': "", 'remaining': self.quantity},
                              )


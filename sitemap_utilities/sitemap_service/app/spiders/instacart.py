import csv
from urlparse import urljoin

import requests
from lxml import etree

from . import SitemapSpider, SitemapSpiderError


class InstacartSitemapSpider(SitemapSpider):
    retailer = 'instacart.com'

    default_login = 'final.fantasy.dev@gmail.com'
    default_password = 'haha123.'
    default_store = 'costco'

    home_url = 'https://www.instacart.com/'
    sign_in_url = 'https://www.instacart.com/accounts/login'
    retailers_url = 'https://www.instacart.com/v3/retailers'
    departments_url = 'https://www.instacart.com/v3/retailers/{retailer_id}/containers'
    department_url = 'https://www.instacart.com/v3/containers/{container}'
    item_url = 'https://www.instacart.com/store/items/{item_id}'

    def task_sitemap_to_item_urls(self, options):
        session = self._sign_in(options)

        retailer_id = self._get_retailer_id(options, session)
        if not retailer_id:
            raise SitemapSpiderError('Store not found')

        departments = self._get_departments(retailer_id, session)

        with open(self.get_file_path_for_result('item_urls.csv'), 'w') as item_urls_file:
            item_urls_csv = csv.writer(item_urls_file)

            item_ids_seen = set()

            for department in departments:
                for item_id in self._load_items(department, session):
                    if item_id not in item_ids_seen:
                        item_url = self.item_url.format(item_id=item_id)

                        item_urls_csv.writerow([item_url])
                        item_ids_seen.add(item_id)

    def _sign_in(self, options):
        self.logger.info('Authentication..')

        session = requests.Session()

        response = session.get(self.home_url)
        self._check_response(response, raise_error=True, session=session)

        tree = etree.HTML(response.content)
        token = tree.xpath(".//meta[@name='csrf-token']/@content")

        if token:
            token = token[0]
        else:
            raise SitemapSpiderError('Can not parse auth token')

        login = options.get('login') or self.default_login
        password = options.get('password') or self.default_password

        sign_in_data = {
            'user': {
                'email': login,
                'password': password
            },
            'authenticity_token': token
        }

        response = session.post(self.sign_in_url, json=sign_in_data, headers={'Accept': 'application/json'})
        self._check_response(response, raise_error=True, session=session)

        self.logger.info('Success')

        return session

    def _get_retailer_id(self, options, session):
        store = options.get('store') or self.default_store
        self.logger.info('Loading retailer id for store: {}'.format(store))

        response = session.get(self.retailers_url)
        self._check_response(response, raise_error=True, session=session)

        retailers = response.json().get('retailers')
        if not retailers:
            raise SitemapSpiderError('List of retailers is empty')

        for retailer in retailers:
            if store in (retailer.get('slug'), retailer.get('name')):
                return retailer.get('id')

    def _get_departments(self, retailer_id, session):
        self.logger.info('Loading departments for retailer id: {}'.format(retailer_id))

        response = session.get(self.departments_url.format(retailer_id=retailer_id))
        self._check_response(response, raise_error=True, session=session)

        containers = response.json().get('containers')
        if not containers:
            raise SitemapSpiderError('List of departments is empty')

        departments = []

        while True:
            if not containers:
                break

            container = containers.pop(0)

            if 'virtual' not in container.get('attributes', []):
                departments.append(container.get('path'))

            if container.get('containers'):
                containers.extend(container['containers'])

        return departments

    def _load_items(self, department, session):
        self.logger.info('Loading items for department: {}'.format(department))

        response = session.get(self.department_url.format(container=department))
        self._check_response(response, raise_error=True, session=session)

        modules = response.json().get('container', {}).get('modules')
        if not modules:
            raise SitemapSpiderError('List of modules is empty')

        start_url = self._get_start_url(modules)

        if start_url:
            start_url = urljoin(self.home_url, start_url)

            self.logger.info('Scraping shelf page: {}'.format(start_url))

            next_page = 1

            while next_page:
                self.logger.info('Page: {}'.format(next_page))

                response = session.get(start_url, params={'page': next_page, 'per': 30})
                self._check_response(response, raise_error=True, session=session)

                data = response.json().get('module_data', {})

                for item in data.get('items', []):
                    yield item.get('id')

                next_page = data.get('pagination', {}).get('next_page')
        else:
            self.logger.warn('There is not shelf url')

    def _get_start_url(self, modules):
        for mod in modules:
            if 'items_grid' in mod.get('types', []):
                return mod.get('async_data_path')

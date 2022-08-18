import csv
import gzip
import logging
import re
from StringIO import StringIO

import lxml.etree
import requests


output_file = 'quill.csv'
sitemap_books = 'https://www.qbbooks.com/sitemap.xml'
sitemap = 'http://www.quill.com/sitemap.xml'

book_url = re.compile('https?://www.qbbooks.com/pages/books/')
sku_url = re.compile('https?://www.quill.com/\w+_SKU_')
product_url = re.compile('https?://www.quill.com/[^/]*/cbs/')
list_url = re.compile('https?://www.quill.com/[^/]*/cbk/')

proxies = {
    # 'http://www.quill.com': 'http://198.199.69.46:8080',
    # 'https://www.quill.com': 'http://198.199.69.46:8080',
}


def clear_tag_name(name):
    return name.split('}', 1)[1] if '}' in name else name


def parse_sitemap(url, raise_error=True, follow=True, **kwargs):
    urls = [url]

    if not kwargs.get('headers'):
        kwargs['headers'] = {'User-Agent': ''}

    while urls:
        next_url = urls.pop(0)
        logging.info('Loading sitemap: {}'.format(next_url))

        for _ in range(3):
            try:
                response = requests.get(next_url, **kwargs)
                if response.status_code != requests.codes.ok:
                    logging.error('Could not load sitemap: {}, code: {}'.format(
                        next_url, response.status_code))
                else:
                    break
            except:
                logging.error('Could not load sitemap')
        else:
            if raise_error:
                raise Exception('Could not load sitemap after retries')
            else:
                logging.error('Could not load sitemap after retries')
                continue

        content = response.content
        if next_url.lower().endswith('.gz'):
            content = gzip.GzipFile(fileobj=StringIO(content)).read()
        xmlp = lxml.etree.XMLParser(recover=True, remove_comments=True,
                                    resolve_entities=False)
        root = lxml.etree.fromstring(content, parser=xmlp)
        type = clear_tag_name(root.tag)

        for elem in root.getchildren():
            for el in elem.getchildren():
                name = clear_tag_name(el.tag)
                if name == 'loc':
                    new_url = el.text.strip() if el.text else ''
                    if not new_url:
                        continue
                    if type == 'sitemapindex':
                        if follow:
                            urls.append(new_url)
                        else:
                            yield new_url
                    elif type == 'urlset':
                        yield new_url.encode('utf-8')


logging.basicConfig(level=logging.INFO)
with open(output_file, 'w') as output:
    writer = csv.writer(output)

    for url in parse_sitemap(sitemap_books, proxies=proxies):
        if book_url.match(url):
            writer.writerow([url])

    for sitemap_url in parse_sitemap(sitemap, follow=False, proxies=proxies):
        is_sku = sku_url.match(sitemap_url)
        for url in parse_sitemap(sitemap_url, proxies=proxies):
            is_product = product_url.match(url)
            if is_sku:
                if is_product:
                    writer.writerow([url])
                else:
                    if list_url.match(url):
                        logging.debug('Ignoring list in sku sitemap: {}'.find(url))
                    else:
                        logging.warning('Unknown link in sku sitemap: {}'.find(url))
            elif is_product:
                logging.warning('Possible product in non-sku sitemap: {}'.find(url))

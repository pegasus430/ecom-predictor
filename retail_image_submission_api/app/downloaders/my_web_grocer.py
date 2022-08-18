import shutil
import traceback
import urllib2
from urlparse import urlparse

import os

from . import ImageSubmissionDownloader, ImageSubmissionDownloaderError


class MyWebGrocerImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'my web grocer'

    def task_images(self, options, products):
        try:
            self.logger.info('[START DOWNLOAD IMAGES]')

            for product in products:
                product_id = product.get('id')

                upc = product.get('upc')

                if not upc:
                    self.logger.error('Product {} has not UPC'.format(product_id))
                    continue

                image_urls = product.get('image_urls')

                if not image_urls:
                    self.logger.warn('Product {} has not images'.format(product_id))
                    continue

                self.logger.debug('Loading primary image for product {}'.format(product_id))

                image_url = image_urls[0]
                image_type = os.path.splitext(urlparse(image_url).path)[1]
                image_name = '{name}{type}'.format(name=self._format_upc(upc), type=image_type)

                try:
                    self.logger.debug('Loading image: {}'.format(image_url))
                    res = urllib2.urlopen(image_url, timeout=60)
                except:
                    self.logger.error('Can not load image {}: {}'.format(image_url, traceback.format_exc()))
                else:
                    if res.getcode() != 200:
                        self.logger.error('Can not load image {}: response code {}, content: {}'.format(
                            image_url, res.getcode(), res.read()))
                    else:
                        with open(self.get_file_path_for_result(image_name), 'wb') as image_file:
                            shutil.copyfileobj(res, image_file)

            self.logger.info('[END DOWNLOAD IMAGES]')
        except:
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise ImageSubmissionDownloaderError('Submission failed')

    def _format_upc(self, upc):
        r = list(reversed(upc))

        check_digit = int(r[0])
        sum_digits = r[1:]

        by3 = [3 * int(x) for i, x in enumerate(sum_digits) if i % 2 == 0]
        by1 = [int(x) for i, x in enumerate(sum_digits) if i % 2 == 1]

        summed_total = sum(by3 + by1) + check_digit

        if summed_total % 10 == 0 and len(upc.lstrip('0')) > 10:
            # remove check digit
            upc = upc[:-1]

        return upc[-11:].zfill(11)

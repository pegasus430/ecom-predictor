import traceback
import urllib2
import shutil
from urlparse import urlparse

import os

from . import ImageSubmissionDownloader, ImageSubmissionDownloaderError


class AmazonImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'amazon.com'

    def task_images(self, options, products):
        try:
            self.logger.info('[START DOWNLOAD IMAGES]')

            for product in products:
                product_id = product.get('id')

                asin = product.get('asin')

                if not asin:
                    self.logger.error('Product {} has not ASIN'.format(product_id))
                    continue

                image_urls = product.get('image_urls')

                if not image_urls:
                    self.logger.warn('Product {} has not images'.format(product_id))
                    continue

                new_images = product.get('new_images')

                if not new_images:
                    self.logger.info('Product {} has not new images. Skipping'.format(product_id))
                    continue

                self.logger.debug('Loading images for product {}'.format(product_id))

                for image_index, image_url in enumerate(image_urls):
                    image_type = os.path.splitext(urlparse(image_url).path)[1]

                    image_name = self._get_image_name(asin, image_index, options.get('naming_conventions', {}))
                    image_name = '{name}{type}'.format(name=image_name, type=image_type)

                    if image_url in new_images:
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

    def _get_image_name(self, asin, index, naming_conventions):
        configurable = naming_conventions.get('configurable')
        other = naming_conventions.get('other')

        if not configurable and not other:
            raise Exception('Naming conventions are empty')

        if index < len(configurable):
            return '{asin}{suffix}'.format(asin=asin, suffix=configurable[index])

        num = index - len(configurable) + 1

        suffix = other.format(SINGLE_NUMBER=num,
                              DOUBLE_NUMBER=format(num, '02d'),
                              A_Z_LETTER=chr(ord('A') - 1 + num))

        return '{asin}{suffix}'.format(asin=asin, suffix=suffix)


class AmazonFreshImageSubmissionDownloader(AmazonImageSubmissionDownloader):
    retailer = 'amazon fresh'


class AmazonPantryImageSubmissionDownloader(AmazonImageSubmissionDownloader):
    retailer = 'amazon pantry'


class AmazonPrimenowImageSubmissionDownloader(AmazonImageSubmissionDownloader):
    retailer = 'amazon primenow'

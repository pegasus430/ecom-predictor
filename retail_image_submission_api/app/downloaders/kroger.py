import json
import re
import traceback
import urllib2

from PIL import Image

from . import ImageSubmissionDownloader, ImageSubmissionDownloaderError


class KrogerImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'kroger.com'

    def task_images(self, options, products):
        try:
            self.logger.info('[START DOWNLOAD IMAGES]')

            for product in products:
                product_id = product.get('id')

                gtin = product.get('gtin')

                if gtin:
                    gtin = self._format_upc(gtin)
                else:
                    self.logger.error('Product {} has not GTIN'.format(product_id))
                    continue

                image_urls = product.get('image_urls')

                if not image_urls:
                    self.logger.warn('Product {} has not images'.format(product_id))
                    continue

                self.logger.debug('Loading images for product {}'.format(product_id))

                for image_index, image_url in enumerate(image_urls[:6], 1):
                    image_type = options.get('image_type', image_url.split('.', 1)[-1])
                    if image_type not in {'jpg', 'png'}:
                        image_type = 'jpg'

                    image_name = '{}-{}.{}'.format(gtin, image_index, image_type)

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
                            image = Image.open(res)

                            if not image.mode.startswith('RGB'):
                                image = image.convert('RGB')

                            image.save(self.get_file_path_for_result(image_name))

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

        return upc[-13:].zfill(13)

import traceback
import urllib2
from PIL import Image

from . import ImageSubmissionDownloader, ImageSubmissionDownloaderError


class TargetImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'instacart.com'

    @staticmethod
    def _get_image_urls(product):
        image_urls = product.get('image_urls')
        return image_urls

    def task_images(self, options, products):
        try:
            self.logger.info('[START DOWNLOAD IMAGES]')

            for product in products:
                product_id = product.get('id')

                name_base = product.get('gtin') or product.get('upc')

                if not name_base:
                    self.logger.error('Product {} - missed gtin/upc'.format(product_id))

                image_urls = self._get_image_urls(product)
                if not image_urls:
                    self.logger.warn('Product {} has not images'.format(product_id))
                    continue

                self.logger.debug('Loading images for product {}'.format(product_id))
                for image_index, image_url in enumerate(image_urls):
                    try:
                        self.logger.debug('Loading image: {}'.format(image_url))
                        res = urllib2.urlopen(image_url, timeout=60)
                    except:
                        self.logger.error('Can not load image {}: {}'.format(image_url, traceback.format_exc()))
                    else:
                        if res.getcode() != 200:
                            self.logger.error(
                                'Can not load image {}: response code {}, content: {}'.format(
                                    image_url,
                                    res.getcode(),
                                    res.read()
                                )
                            )
                        else:
                            image = Image.open(res)
                            if not image.mode.startswith('RGB'):  # jpeg/png type
                                image = image.convert('RGB')

                            image_type = options.get('image_type', 'jpg')

                            if image_index == 0:
                                image_name = '{}.{}'.format(name_base, image_type)
                            else:
                                image_name = '{}_{:02}.{}'.format(name_base, image_index, image_type)

                            image.save(self.get_file_path_for_result(image_name), quality=80)

            self.logger.info('[END DOWNLOAD IMAGES]')
        except:
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise ImageSubmissionDownloaderError('Submission failed')

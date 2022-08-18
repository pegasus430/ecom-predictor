import traceback
import urllib2
from PIL import Image

from . import ImageSubmissionDownloader, ImageSubmissionDownloaderError


class TargetImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'target.com'

    def task_images(self, options, products):
        try:
            self.logger.info('[START DOWNLOAD IMAGES]')

            for product in products:
                product_id = product.get('id')

                tcin = product.get('tcin')

                if not tcin:
                    self.logger.error('Product {} has not TCIN'.format(product_id))
                    continue

                image_urls = product.get('image_urls')

                if not image_urls:
                    self.logger.warn('Product {} has not images'.format(product_id))
                    continue

                new_images = product.get('new_images') or []

                self.logger.debug('Loading images for product {}'.format(product_id))

                for image_index, image_url in enumerate(image_urls):
                    if options.get('differences_only') and image_url not in new_images:
                        continue

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

                            if options.get('image_resize'):
                                width, height = image.size
                                dimension = options.get('image_min_side_dimension')

                                if dimension and width != height and width >= dimension and height >= dimension:
                                    ratio = float(dimension) / max(width, height)

                                    width = int(width * ratio)
                                    height = int(height * ratio)

                                    image = image.resize((width, height), Image.LANCZOS)

                                    new_image = Image.new('RGB', (dimension, dimension), (255, 255, 255))
                                    new_image.paste(image, ((dimension - width) / 2, (dimension - height) / 2),
                                                    image if image.mode == 'RGBA' else None)

                                    image = new_image

                            image_type = options.get('image_type', 'jpg')

                            if image_index == 0:
                                image_name = '{}.{}'.format(tcin, image_type)
                            else:
                                image_name = '{}_{:02}.{}'.format(tcin, image_index, image_type)

                            image.save(self.get_file_path_for_result(image_name))

            self.logger.info('[END DOWNLOAD IMAGES]')
        except:
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise ImageSubmissionDownloaderError('Submission failed')

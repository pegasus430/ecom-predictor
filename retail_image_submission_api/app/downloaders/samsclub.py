import json
import shutil
import traceback
import urllib2
from urlparse import urlparse

import os

from . import ImageSubmissionDownloader, ImageSubmissionDownloaderError


class SamsclubImageSubmissionDownloader(ImageSubmissionDownloader):
    retailer = 'samsclub.com'

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

                image_tags = product.get('image_tags') or {}
                if image_tags:
                    image_urls = self._sort_image_urls(image_urls, image_tags)

                new_images = product.get('new_images')

                if not new_images:
                    self.logger.info('Product {} has not new images. Skipping'.format(product_id))
                    continue

                self.logger.debug('Loading images for product {}'.format(product_id))

                for image_index, image_url in enumerate(image_urls[:9]):
                    image_type = os.path.splitext(urlparse(image_url).path)[1]

                    image_name = self._get_image_name(upc, image_index)
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

    def _get_image_name(self, upc, index):
        name = self._format_upc(upc)

        suffix = chr(ord('A') + index)

        return '{name}_{suffix}'.format(name=name, suffix=suffix)

    def _sort_image_urls(self, image_urls, image_tags):
        sorted_image_urls = []
        nutrition_image_urls = []

        for image_url in image_urls:
            tags = image_tags.get(image_url)
            if tags:
                type_tags = tags.get('type_tags') or []

                if isinstance(type_tags, basestring):
                    try:
                        type_tags = json.loads(type_tags)
                    except:
                        type_tags = []

                if 'Nutrition Facts' in type_tags:
                    nutrition_image_urls.append(image_url)
                    continue

            sorted_image_urls.append(image_url)

        if nutrition_image_urls:
            sorted_image_urls[1:1] = nutrition_image_urls

        return sorted_image_urls

    def task_videos(self, options, products):
        try:
            self.logger.info('[START DOWNLOAD VIDEOS]')

            for product in products:
                product_id = product.get('id')

                upc = product.get('upc')

                if not upc:
                    self.logger.error('Product {} has not UPC'.format(product_id))
                    continue

                videos = product.get('videos')

                if not videos:
                    self.logger.warn('Product {} has not videos'.format(product_id))
                    continue

                video_urls = [video['video_url'] for video in videos]

                new_videos = product.get('new_videos')

                if not new_videos:
                    self.logger.info('Product {} has not new videos. Skipping'.format(product_id))
                    continue

                new_videos = [video['video_url'] for video in new_videos]

                self.logger.debug('Loading videos for product {}'.format(product_id))

                for video_index, video_url in enumerate(video_urls[:2]):
                    video_type = os.path.splitext(urlparse(video_url).path)[1]

                    video_name = self._get_video_name(upc, video_index)
                    video_name = '{name}{type}'.format(name=video_name, type=video_type)

                    if video_url in new_videos:
                        try:
                            self.logger.debug('Loading video: {}'.format(video_url))
                            res = urllib2.urlopen(video_url, timeout=300)
                        except:
                            self.logger.error('Can not load video {}: {}'.format(video_url, traceback.format_exc()))
                        else:
                            if res.getcode() != 200:
                                self.logger.error('Can not load video {}: response code {}, content: {}'.format(
                                    video_url, res.getcode(), res.read()))
                            else:
                                with open(self.get_file_path_for_result(video_name), 'wb') as video_file:
                                    shutil.copyfileobj(res, video_file)

            self.logger.info('[END DOWNLOAD VIDEOS]')
        except:
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise ImageSubmissionDownloaderError('Submission failed')

    def _get_video_name(self, upc, index):
        name = self._format_upc(upc)

        suffix = chr(ord('A') + index)

        return '{name}_VIDEO_{suffix}'.format(name=name, suffix=suffix)

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

# -*- coding: utf-8 -*-
import requests
import json
import shutil
import boto
import re
import time
import xlrd
import os
import logging
import zipfile

from boto.s3.key import Key
from . import SubmissionSpider, SubmissionSpiderError


class InstacartSubmissionSpider(SubmissionSpider):
    retailer = 'instacart.com'

    driver_engine = None  # don't use web driver
    pattern = re.compile('(?!2\sGo|2O|2Go|[0-9]+%)([0-9].+)')
    lays_list = [u"Frito-Lay", u"Frito-Lay's", u"Frito-Lays", u"FritoLay", u"FritoLays",
                 u"FritoLay's", u"Frito Lay", u"Frito Lay's", u"Frito Lays", u"Lay's", u"Frito Lay Variety Pack",
                 u"Frito-Lay’s", u"FritoLay’s", u"Frito Lay’s", u"Lay’s"]

    def __init__(self, feed_id, resources_dir, sandbox=False, logger=None):
        super(InstacartSubmissionSpider, self).__init__(
            feed_id, resources_dir, sandbox, logger)
        if sandbox:
            self.endpoint = 'https://catalog-api.instacart.com/api/v1/content?test=true'
        else:
            self.endpoint = 'https://catalog-api.instacart.com/api/v1/content'

        self.logger.setLevel(logging.INFO)
        self.bucket = 'bulk-import-pepsico'

    def cleanhtml(self, raw_html):
        if not raw_html:
            return raw_html
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, '', raw_html)
        return cleantext

    def fill_json(self, product):
        product_dict = {}
        core_info, description, images, other = {}, {}, {}, {}
        upc = product.get("upc")
        if not upc:
            self.logger.error(u"Product {} hasn't scan code.".format(product.get("id")))
            return

        core_info["scan_code"] = upc
        name = product.get("product_name")
        if name is None:
            self.logger.error("No name for {}".format(product.get("id")))
            return {}

        core_info["brand_name"] = product.get("brand", "")

        description["marketing_info"] = product.get("description", "")
        desc = product.get("long_description", "")
        if desc:
            description["other"] = self.cleanhtml(desc)
        img = product.get("image_urls", [])
        if img:
            images["main"] = img[0]
            if "amazonaws" not in images["main"]:
                self.logger.error(u"Not amazon image as main ({}), for {}".format(images["main"], name))
                return {}

        other["client_id"] = self.client_id
        product_dict["core_info"] = core_info
        product_dict["description"] = description
        product_dict["images"] = images
        product_dict["other"] = other
        data_added = self.add_xls_info(product_dict)
        core_info["name"] = self.remove_brand(
            name, core_info["brand_name"])
        core_info["name"] = self.clear_name(core_info["name"])

        if data_added:
            return product_dict
        else:
            self.logger.error(u"No data in excel file for {}".format(name))
            return {}

    def clear_name(self, name):
        clean_name = re.sub(self.pattern, '', name).strip()
        if clean_name.endswith(",") or clean_name.endswith("(") or clean_name.endswith("-"):
            clean_name = clean_name[:-1]

        return clean_name

    def remove_brand(self, name, brand):
        if brand is None:
            return name
        name_normal = name.upper()
        brand_normal = brand.upper()
        if name_normal.startswith(brand_normal):
            name = name_normal.replace(brand_normal, "").title()

        for lays_brand in self.lays_list:
            lb_up = lays_brand.upper()
            if name_normal.startswith(lb_up):
                name = name_normal.replace(lb_up, "").title()

        name = name.strip()
        return name

    @staticmethod
    def _get_product_id(data):
        return data.get("core_info").get("scan_code")

    @staticmethod
    def get_auth_headers(token):
        headers = {"Authorization": "Token {}".format(
            token), "Content-Type": "application/json"}
        return headers

    def upload(self, data, headers):
        for _ in range(10):
            response = requests.post(self.endpoint, headers=headers, data=json.dumps(data))
            self.logger.info(response.text)
            if response.status_code == 201 or response.status_code == 202:
                self.logger.info("Upload {} successful, code {}".format(
                    self._get_product_id(data), response.json()))
                return
            elif response.status_code == 401:
                self.logger.error("Unauthorized")
                raise SubmissionSpiderError("Unathorized")
            elif response.status_code == 400:
                self.logger.error("Bad request. Your JSON for {} is wrong. Reason {}".format(
                    self._get_product_id(data), response.json()))
                return
            elif response.status_code == 427:
                time.sleep(60)
        raise SubmissionSpiderError(
            "Error 427. After ten attempts we have no success. Stop.")

    def task_content(self, options, products, server, **kwargs):
        token = options.get("token")
        if not token:
            self.logger.error("Authorisation token is absent. Upload impossible")
            raise SubmissionSpiderError("Authorisation token is absent. Upload impossible")

        self.client_id = options.get("client_id")
        if not self.client_id:
            self.logger.error("Client ID is not provided. Upload impossible.")
            raise SubmissionSpiderError(
                "Client ID is not provided. Upload impossible.")

        self.logger.info("Transforming JSON for Instacart")

        headers = self.get_auth_headers(token)

        for product in products:
            insta_json = self.fill_json(product)
            if insta_json:
                self.logger.info("Conversion succesful {}".format(self._get_product_id(insta_json)))

                # converting images and moving them to S3 server
                insta_json['images'] = self._task_images(server=server, product=product)

                filepath = self.get_file_path_for_result(
                    name=self._get_product_id(insta_json))

                with open("{}.json".format(filepath), "w") as filename:
                    json.dump(insta_json, filename)
                self.logger.info("Uploading {} data".format(product.get("id")))
                self.upload(insta_json, headers)

    def _task_images(self, server, product):
        criteria = {
            'filter': {
                'products': product['id']
            }
        }
        images = self._export_media(criteria, server)
        s3_urls = []

        with zipfile.ZipFile(images, 'r') as zip_file:
            for image in zip_file.infolist():
                image_filename = self.get_file_path_for_result(image.filename, append=False)

                with open(image_filename, 'wb') as image_file:
                    shutil.copyfileobj(zip_file.open(image), image_file)
                    s3_url = self._upload_image(image_file, image_file.split('/')[-1])
                    if not s3_url:
                        self.logger.error('Image ({0}) for product {1} wasnt loaded'.format(image_file, product['id']))
                    else:
                        s3_urls.append(s3_url)
        return s3_urls

    def _upload_image(self, filename, image_name):
        """
        upload image to S3 server
        """

        def _get_content_type(_name):
            ext = _name.split('.')[-1]
            ext = ext.strip().lower()
            if ext == 'png':
                return 'image/png'
            else:
                return 'image/jpeg'

        content_type = _get_content_type(image_name)
        try:
            s3_conn = boto.connect_s3()
            s3_bucket = s3_conn.get_bucket(self.bucket, validate=False)

            s3_key = Key(bucket=s3_bucket, name=image_name)
            s3_key.set_metadata('content-type', content_type)

            # if not s3_key.exists():
            self.logger.info('Uploading - {}'.format(image_name))
            s3_key.set_contents_from_filename(filename)
            s3_url = s3_key.generate_url(expires_in=0, query_auth=False)
            s3_url = s3_url.split('?')[0]
            return s3_url
        except Exception as e:
            self.logger.error('Can not upload image {} to S3: {}'.format(filename, e))
        return False

    def add_xls_info(self, product_dict):
        datafile = xlrd.open_workbook(
            'Content Analytics Data Pub 06-14-2017.xls')
        product_id = self._get_product_id(product_dict)
        core = product_dict["core_info"]
        sheet = datafile.sheet_by_index(0)
        data_added = False
        for row in sheet.get_rows():
            if product_id in row[0].value:
                core["size_value"] = str(row[11].value)
                core["size_uom"] = str(row[12].value)
                core["size_container"] = str(row[13].value)
                core["unit_container"] = str(row[9].value)
                core["unit_value"] = str(int(row[10].value))
                core["unit_uom"] = str(row[13].value)
                core["brand_name"] = str(row[3].value)
                data_added = True

        return data_added

import requests
import json
import base64

from . import SubmissionSpider, SubmissionSpiderError


PRODUCT_NAME = '0d96a759-6ab3-424c-9b73-3aec0d09d2f6'
MFG_BRAND = '29d438d9-64f2-4623-8f4e-09f9368e93bb'
BULLET01 = '3b8d7d7e-9ff9-4b2b-99ca-57a1ba19eb94'
BULLET02 = '15271107-6854-40a9-bcd6-b320407d8544'
BULLET03 = 'fed33381-f352-458d-9732-11e1053008c2'
BULLET04 = '8736c9b6-a1db-4bd9-a9b5-938234b899ec'
BULLET05 = 'c69c774b-774d-4887-9656-c77807342c64'
BULLET06 = '1905c003-bc16-459c-848d-930ce2db71bb'
BULLET07 = 'db7ffb34-7fcf-4167-a8c3-1af4ae8d981a'
BULLET08 = 'dc178130-aeed-4c0f-9fc4-39521ded5adf'
BULLET09 = '3acca797-8968-45f5-9b2c-2bcbbe35341a'
BULLET10 = 'e78a9b12-e44a-4dd0-9052-e466a3d0249d'
BULLET11 = '543ab816-5598-44fb-92cd-fc131ed7b8df'
BULLET12 = '15b1aa18-6b8e-4d70-afed-19746853eb5b'
BULLET13 = '543f5200-b1f2-4826-b9aa-547c7341f520'
BULLET14 = 'bbebf017-9c1f-4c78-bd49-c2981e8a04d1'
BULLET15 = '823d8237-b5fe-41dc-aa74-0c7ae9048267'
BULLET16 = '8cd2457b-d47e-4bfe-b1fb-38eef56eb94d'
BULLET17 = 'd87df1c3-50ef-4720-894a-06c714e6e1ed'
BULLET18 = 'a68db77c-c72e-45ed-b51d-497f218c0dc9'

fields_mapping = {
    'product_name': PRODUCT_NAME,
}


class HomeDepotSubmissionSpider(SubmissionSpider):
    retailer = 'homedepot.com'
    driver_engine = None  # don't use web driver
    submission_filename = 'homedepot.json'

    client_id = 'CA_Stanley'
    api_key = 's23jk4h23jh'

    default_channel_id = "homedepot-thd-qa"
    workflow_mode = "publish"
    import_mode = "update_and_create"
    mapping_mode = "channel_known_attributes_only"
    __THD_GLN = "4009990000003"

    upload_endpoint = 'https://tagglo.io/api/import/v1/feeds/salsify_v1'
    job_status_endpoint = 'http://tagglo.io/api/import/v1/jobs/{job_id}'
    product_status_endpoint = 'https://tagglo.io/api/channels/v1/{channel}/status/products/{id}'
    submit_endpoint = 'https://tagglo.io/api/submit/v1/channels/{channel}/products/'

    # job statuses
    JOB_COMPLETE = 'Completed'

    end_of_job_states = [JOB_COMPLETE]

    def _build_hd_product(self, product):
        home_depot_product = {
            '__CATEGORY': product['category_name'],
            '__ID': self._get_product_id(product),
            '__NAME': product['product_name'],
            '__THD_GLN': self.__THD_GLN,
        }
        for attr in product.keys():
            if attr in fields_mapping:
                attr_id = fields_mapping[attr]
                home_depot_product[attr_id] = product[attr]
        return home_depot_product

    def _get_auth_headers(self):
        token = base64.b64encode("{}:{}".format(self.client_id, self.api_key))
        headers = {"Content-Type": "application/json", "Authorization": "Basic {}".format(token)}
        return headers

    def _get_job_status(self, job_id, r_headers):
        job_status_url = self.job_status_endpoint.format(job_id=job_id)
        job_status_response = requests.get(job_status_url, headers=r_headers)
        self.logger.debug('Job (data import) status response: {}'.format(job_status_response.content))

        if job_status_response.status_code not in [200, ]:
            raise SubmissionSpiderError(
                "Job status not available. Server return {} error".format(job_status_response.status_code)
            )
        status = job_status_response.json().get('status')
        if not status:
            raise SubmissionSpiderError("Job status not found in response.")
        return status

    def _check_product_status(self, product_id, r_headers, options):
        product_status_url = self.product_status_endpoint.format(channel=self._get_channel(options), id=product_id)
        prd_status_response = requests.get(product_status_url, headers=r_headers)
        self.logger.debug('Product ({}) status response: {}'.format(product_id, prd_status_response.content))

        if prd_status_response.status_code not in [200, ]:
            raise SubmissionSpiderError(
                "Product status not available. Server return {} error".format(prd_status_response.status_code)
            )
        errors = prd_status_response.json().get('dataErrors')
        if errors:
            self.logger.warning('Product {0} import data error. Data errors:'.format(product_id))
            for key, value in errors.iteritems():
                self.logger.warning('\tAttribute id {0}, message: {1}'.format(key, value))
            # TODO should we continue processing?
            # raise SubmissionSpiderError("Product import data error.")
            return False
        return True

    @staticmethod
    def _get_product_id(product):
        if '__ID' in product:
            return product['__ID']
        if 'id' not in product:
            raise SubmissionSpiderError('Product without "id" field.')
        return product['id']

    def _get_channel(self, options):
        if 'channel' not in options:
            return self.default_channel_id
        return options['channel']

    def task_content(self, options, products, *args, **kwargs):
        self.logger.info("Preparing HomeDepot JSON")
        headers = self._get_auth_headers()

        hd_data = {
            'channelId': self._get_channel(options),
            'workflowMode': self.workflow_mode,
            'importMode': self.import_mode,
            'mappingMode': self.mapping_mode,
            'products': [],
        }

        # upload products
        self.data.setdefault('products', [])
        for product in products:
            if options.get('products_ready'):  # if products were posted by user
                hd_data['products'].append(product)
                self.data['products'].append({'id': self._get_product_id(product)})
            else:
                hd_data['products'].append(self._build_hd_product(product))
                self.data['products'].append({'id': self._get_product_id(product)})

        json_filename = self.get_file_path_for_result(self.submission_filename)
        with open(json_filename, 'wb') as json_file:
            json.dump(hd_data, json_file, indent=2)
        response = requests.post(self.upload_endpoint, data=json.dumps(hd_data), headers=headers)

        self.logger.debug('Products upload (data import) response: {}'.format(response.content))

        if response.status_code not in [200, 201, 202]:
            raise SubmissionSpiderError("File was not uploaded. Server return {} error".format(response.status_code))

        job_id = response.json().get('jobRef')
        if not job_id:
            raise SubmissionSpiderError("Job reference not found in response.")

        self.data['job_id'] = job_id
        self.async_check_required = True

        self.logger.info('Products were uploaded')

    def task_check(self, options, **kwargs):
        self.logger.info('Checking submission status')

        job_id = options['job_id']
        headers = self._get_auth_headers()

        # Check job status
        job_status = self._get_job_status(job_id, headers)
        self.logger.info('Current submission status: "{}"'.format(job_status))

        # we can submit products only if upload job is ready
        if job_status not in self.end_of_job_states:
            return

        if job_status != self.JOB_COMPLETE:
            self.logger.debug('Bad status from import data job: {}'.format(job_status))
            raise SubmissionSpiderError("Bad job status returned.")

        # Check products
        products = options['products']
        products_ids = []
        for product in products:
            product_id = self._get_product_id(product)
            product_state = self._check_product_status(product_id, headers, options)
            if product_state:
                products_ids.append(product_id)

        # Submit
        if products_ids:
            submit_url = self.submit_endpoint.format(channel=self._get_channel(options))
            self.logger.debug('Submitting products... (ids are {})'.format(json.dumps(products_ids)))
            response = requests.post(submit_url, data=json.dumps(products_ids), headers=headers)
            self.logger.debug('Submit response: {}'.format(response.content))

            if response.status_code not in [200, 201, 202]:
                raise SubmissionSpiderError("Products submit error. Server return {}.".format(response.status_code))
            else:
                response_data = response.json()
                submission_id = response_data.get('submissionId') or None
                if not submission_id:
                    raise SubmissionSpiderError("Products submit error. Server don't return submissionId.")
                self.logger.info('Products were uploaded and submitted. Submission id is "{}"'.format(submission_id))
        else:
            raise SubmissionSpiderError("Products submit error: no products to submit.")

        # stop processing once products were submitted
        self.async_check_required = False

    def task_user_uploaded(self, options, **kwargs):
        self.logger.info("Performing submission of user uploaded products")
        products = options.get('products')
        if not products:
            self.logger.warning("Products not provided in options. Exiting with error")
            raise SubmissionSpiderError("No products in options.")

        self.logger.info("Products for processing: {}".format(len(products)))
        self.logger.info("Redirecting to task_content")
        options['products_ready'] = True
        self.task_content(options, products)


if __name__ == '__main__':

    iss = HomeDepotSubmissionSpider("Feed", "/home/alex/temp", sandbox=False)
    res = requests.get(
        'https://energizer.contentanalyticsinc.com/api/products?'
        'api_key=d28ab4cd79d9cbb75467c267614f0266d2220b4f&'
        'filter[search][field]=upc&filter[search][value]=608938171931'
    )
    mc_data = res.json()
    test_dict = {}
    iss.task_content(test_dict, mc_data["products"], None)
    test_dict.update(iss.data)
    iss.task_check(test_dict)

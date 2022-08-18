import shutil
from datetime import datetime
from urlparse import urlparse

import pysftp
import requests

from . import SubmissionSpider, SubmissionSpiderError


class DollarGeneralSubmissionSpider(SubmissionSpider):
    retailer = 'dollargeneral.com'
    driver_engine = None  # don't use web driver

    def _template_export(self, caids, server_name):
        url = 'http://bulk-import.contentanalyticsinc.com/mc_export'

        data = {
            'retailer': 'dollargeneralsubmission',
            'server': server_name
        }

        files = {'file': ('caids.csv', 'CAID\n{}'.format('\n'.join(caids)))}

        response = requests.post(url, data=data, files=files).json()

        if response.get('error'):
            raise SubmissionSpiderError(response.get('message'))

        return response.get('file')

    def _template_name(self, options, server_name):
        name = '{ip}_{supplier}_{date}.csv'.format(
            ip=options.get('destination_ip', '34.193.31.95'),
            supplier=server_name,
            date=datetime.now().strftime('%Y%m%d%H%M%S')
        )

        return name

    def _template_upload(self, options, url, name):
        template_filename = self.get_file_path_for_result(name)
        response = requests.get(url, stream=True)

        with open(template_filename, 'wb') as template_file:
            shutil.copyfileobj(response.raw, template_file)

        if not self.sandbox and options.get('do_submit'):
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None

            with pysftp.Connection(options.get('sftp_ip_address'),
                                   username=options.get('sftp_username'),
                                   password=options.get('sftp_password'),
                                   cnopts=cnopts) as sftp:
                with sftp.cd(options.get('sftp_dir')):
                    sftp.put(template_filename, name)

    def task_content(self, options, products, server, **kwargs):
        caids = []

        for product in products:
            product_id = product.get('id')

            if product_id:
                caids.append(product_id)

        if not caids:
            raise SubmissionSpiderError('List of CAIDs is empty')

        server_url = server.get('url', '')
        server_url_parts = urlparse(server_url)
        server_name = server_url_parts.netloc.split('.')[0]

        if not server_name:
            raise SubmissionSpiderError('Server name is empty')

        template_name = self._template_name(options, server_name)

        self.logger.info('Template exporting')
        template_url = self._template_export(caids, server_name)

        self.logger.info('Template saving')
        self._template_upload(options, template_url, template_name)

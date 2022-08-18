from datetime import datetime

import pysftp
import requests

from . import SubmissionSpider, SubmissionSpiderError


class GoogleMcSubmissionSpider(SubmissionSpider):
    retailer = 'google.com'
    driver_engine = None  # don't use web driver

    def _template_export(self, caids, server_url, client_id):
        url = 'http://converters.contentanalyticsinc.com/converter/api'

        data = {
            'input_type': 'template',
            'output_type': 'googlemanufacturer',
            'server': server_url,
            'target_client_id': client_id
        }

        files = {'caids_file': ('caids.csv', 'CAID\n{}'.format('\n'.join(caids)))}

        response = requests.post(url, data=data, files=files)

        if response.status_code != requests.codes.ok:
            response = response.json()

            raise SubmissionSpiderError(response.get('message'))

        return response.content

    def _template_name(self):
        name = 'google_{date}.xml'.format(
            date=datetime.now().strftime('%Y%m%d%H%M%S')
        )

        return name

    def _template_upload(self, options, content, name):
        template_filename = self.get_file_path_for_result(name)

        with open(template_filename, 'wb') as template_file:
            template_file.write(content)

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

        server_url = server.get('url')

        if not server_url:
            raise SubmissionSpiderError('Server url is empty')

        missing_options = {'sftp_ip_address', 'sftp_username', 'sftp_password', 'sftp_dir'} - set(options.keys())
        if missing_options:
            raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        template_name = self._template_name()

        self.logger.info('Template exporting')
        template_content = self._template_export(caids, server_url, options.get('client_id'))

        self.logger.info('Template saving')
        self._template_upload(options, template_content, template_name)

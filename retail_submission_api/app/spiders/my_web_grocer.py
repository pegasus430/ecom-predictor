import traceback
import boto
import shutil
import requests
import time
import zipfile
import csv
import pysftp
import os

from datetime import datetime
from urlparse import urlparse

from . import SubmissionSpider, SubmissionSpiderError


class MyWebGrocerSubmissionSpider(SubmissionSpider):
    retailer = 'my web grocer'
    driver_engine = None  # don't use web driver

    def _template_export(self, caids, server_name):
        url = 'http://bulk-import.contentanalyticsinc.com/mc_export'

        data = {
            'retailer': 'my web grocer',
            'server': server_name
        }

        files = {'file': ('caids.csv', 'CAID\n{}'.format('\n'.join(caids)))}

        response = requests.post(url, data=data, files=files).json()

        if response.get('error'):
            raise SubmissionSpiderError(response.get('message'))

        return response.get('file')

    def _template_name(self, supplier_name):
        name = 'Content Submission {date} {time}.xlsx'.format(
            date=datetime.now().strftime('%m-%d-%Y'),
            time=int(time.time())
        )

        if supplier_name:
            name = supplier_name + ' ' + name

        return name

    def _send_email(self, subject, body, to, cc=None):
        try:
            ses = boto.connect_ses()

            ses.send_email(
                source='retailer@contentanalyticsinc.com',
                subject=subject,
                body=body,
                to_addresses=to,
                cc_addresses=cc
            )

            return True
        except:
            self.logger.error('Can not send email: {}'.format(traceback.format_exc()))
            return False

    def _send_template(self, template, sftp_settings):
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        with pysftp.Connection(sftp_settings.get('sftp_ip_address'),
                               username=sftp_settings.get('sftp_username'),
                               password=sftp_settings.get('sftp_password'),
                               cnopts=cnopts) as sftp:

            with sftp.cd(sftp_settings.get('sftp_dir')):
                today_dir = datetime.now().strftime('%m-%d-%Y')

                if not sftp.exists(today_dir):
                    sftp.mkdir(today_dir)

                with sftp.cd(today_dir):
                    sftp.put(template, os.path.split(template)[-1])

    def _get_server_name(self, server_url):
        server_url_parts = urlparse(server_url)

        return server_url_parts.netloc.split('.')[0]

    def task_text(self, options, products, server, **kwargs):
        self.task_content(options, products, server, **kwargs)

    def task_content(self, options, products, server, **kwargs):
        caids = []

        for product in products:
            product_id = product.get('id')

            if product_id:
                caids.append(product_id)

        if not caids:
            raise SubmissionSpiderError('List of CAIDs is empty')

        server_name = self._get_server_name(server.get('url', ''))

        if not server_name:
            raise SubmissionSpiderError('Server name is empty')

        self.logger.info('Template exporting')
        template_url = self._template_export(caids, server_name)

        supplier_name = options.get('supplier_name')

        self.logger.info('Template saving')
        template_filename = self.get_file_path_for_result(self._template_name(supplier_name))
        response = requests.get(template_url, stream=True)

        with open(template_filename, 'wb') as template_file:
            shutil.copyfileobj(response.raw, template_file)

        self.logger.info('Template sending')

        subject = 'My Web Grocer Update content{for_supplier}'.format(
            for_supplier=' for {}'.format(supplier_name) if supplier_name else ''
        )

        body = 'Content Update Template{for_supplier} has been sent to My Web Grocer SFTP server, ' \
               'username: content_analytics'.\
            format(for_supplier=' for {}'.format(supplier_name) if supplier_name else '')

        if not self.sandbox and options.get('do_submit'):
            self._send_template(template_filename, options)

            result = self._send_email(subject, body, 'customersupport@mywebgrocer.com', options.get('email_recipient'))
        else:
            if 'qa' in options:
                self._send_template(template_filename, options['qa'])

            subject = 'TEST SUBMISSION. ' + subject

            result = self._send_email(subject, body, 'support@contentanalyticsinc.com')

        if not result:
            raise SubmissionSpiderError('Email sending error')

        self.logger.info('Email was sent')

    def task_images(self, options, products, server, criteria, **kwargs):
        images = self._export_media(criteria, server)

        supplier_name = options.get('supplier_name')

        subject = 'My Web Grocer Image content update{for_supplier}'.format(
            for_supplier=' for {}'.format(supplier_name) if supplier_name else ''
        )

        body = 'Content Update Images{for_supplier} has been sent to My Web Grocer SFTP server, ' \
               'username: content_analytics.'.\
            format(for_supplier=' for {}'.format(supplier_name) if supplier_name else '')

        if not self.sandbox and options.get('do_submit'):
            self._send_images(images, supplier_name, options)

            result = self._send_email(subject, body, 'customersupport@mywebgrocer.com', options.get('email_recipient'))
        else:
            if 'qa' in options:
                self._send_images(images, supplier_name, options['qa'])

            subject = 'TEST SUBMISSION. ' + subject

            result = self._send_email(subject, body, 'support@contentanalyticsinc.com')

        if not result:
            raise SubmissionSpiderError('Email sending error')

        self.logger.info('Email was sent')

    def _send_images(self, images, supplier_name, sftp_settings):
        self.logger.info('Sending images')

        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        with pysftp.Connection(sftp_settings.get('sftp_ip_address'),
                               username=sftp_settings.get('sftp_username'),
                               password=sftp_settings.get('sftp_password'),
                               cnopts=cnopts) as sftp:

            with sftp.cd(sftp_settings.get('sftp_dir')):
                today_dir = datetime.now().strftime('%m-%d-%Y')

                if not sftp.exists(today_dir):
                    sftp.mkdir(today_dir)

                with sftp.cd(today_dir):
                    supplier_dir = '{}MWG Images'.format(supplier_name + ' ' if supplier_name else '')

                    if not sftp.exists(supplier_dir):
                        sftp.mkdir(supplier_dir)

                    with sftp.cd(supplier_dir):
                        with zipfile.ZipFile(images, 'r') as zip_file:
                            for image in zip_file.infolist():
                                sftp.putfo(zip_file.open(image), image.filename)

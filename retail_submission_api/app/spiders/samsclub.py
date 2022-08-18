import ftplib
import zipfile

import os
import pysftp
import traceback
import boto
import shutil
import requests

from datetime import datetime
from urlparse import urlparse
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart

from . import SubmissionSpider, SubmissionSpiderError


class SamsclubSubmissionSpider(SubmissionSpider):
    retailer = 'samsclub.com'
    driver_engine = None  # don't use web driver

    def _task_images(self, options, products, server, criteria, **kwargs):
        missing_options = {'ftp_server', 'ftp_username', 'ftp_password', 'ftp_dir'} - set(options.keys())
        if missing_options:
            raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        images = self._export_media(criteria, server)

        self.logger.info('Sending images: {}'.format(images))
        self._send_images(images, options)

        self.logger.info('Done')

    def _send_images(self, images, options):
        if not self.sandbox and options.get('do_submit'):
            server = ftplib.FTP(options['ftp_server'])
            server.login(options['ftp_username'], options['ftp_password'])

            ftp_dir = options['ftp_dir']

            if isinstance(ftp_dir, dict):
                ftp_dir = ftp_dir.get('images')

            with zipfile.ZipFile(images, 'r') as zip_file:
                for image in zip_file.infolist():
                    server.storbinary('STOR {}'.format(os.path.join(ftp_dir, image.filename)),
                                      zip_file.open(image))
        else:
            self._send_to_qa_server(images, options)

    def task_videos(self, options, products, server, criteria, **kwargs):
        missing_options = {'ftp_server', 'ftp_username', 'ftp_password', 'ftp_dir'} - set(options.keys())
        if missing_options:
            raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        videos = self._export_media(criteria, server, media_type='videos')

        self.logger.info('Sending videos: {}'.format(videos))
        self._send_videos(videos, options)

        self.logger.info('Done')

    def _send_videos(self, videos, options):
        if not self.sandbox and options.get('do_submit'):
            server = ftplib.FTP(options['ftp_server'])
            server.login(options['ftp_username'], options['ftp_password'])

            ftp_dir = options['ftp_dir']

            if isinstance(ftp_dir, dict):
                ftp_dir = ftp_dir.get('videos')

            with zipfile.ZipFile(videos, 'r') as zip_file:
                for video in zip_file.infolist():
                    server.storbinary('STOR {}'.format(os.path.join(ftp_dir, video.filename)),
                                      zip_file.open(video))
        else:
            self._send_to_qa_server(videos, options)

    def _send_to_qa_server(self, files, options):
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None

        with pysftp.Connection(options['qa']['sftp_ip_address'],
                               username=options['qa']['sftp_username'],
                               password=options['qa']['sftp_password'],
                               cnopts=cnopts) as sftp:
            with sftp.cd(options['qa']['sftp_dir']):
                with zipfile.ZipFile(files, 'r') as zip_file:
                    for video in zip_file.infolist():
                        sftp.putfo(zip_file.open(video), video.filename)

    def task_media(self, options, products, server, criteria, **kwargs):
        errors = []

        try:
            self._task_images(options, products, server, criteria, **kwargs)
        except SubmissionSpiderError as e:
            self.logger.warn(e.message)
            errors.append(e.message)

        try:
            self.task_videos(options, products, server, criteria, **kwargs)
        except SubmissionSpiderError as e:
            self.logger.warn(e.message)
            errors.append(e.message)

        if len(errors) == 2:
            raise SubmissionSpiderError(', '.join(errors))

    def task_images(self, options, products, server, criteria, **kwargs):
        self.task_media(options, products, server, criteria, **kwargs)

    def task_text(self, options, products, server, criteria, **kwargs):
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

        missing_options = {'email_recipient'} - set(options.keys())
        if missing_options:
            raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

        self.logger.info('Template exporting')
        template_url = self._template_export(caids, server_name)

        self.logger.info('Template saving')
        template_filename = self.get_file_path_for_result(self._template_name())
        response = requests.get(template_url, stream=True)

        with open(template_filename, 'wb') as template_file:
            shutil.copyfileobj(response.raw, template_file)

        self.logger.info('Template sending')

        subject = 'Sam\'s Club Content Submission - {date}'.format(
            date=datetime.now().strftime('%Y-%m-%d')
        )

        body = 'Please find the content updates in the attached file.'

        if not self.sandbox and options.get('do_submit'):
            result = self._template_send(
                subject, body, options.get('email_recipient'), template_filename)
        else:
            subject = 'TEST SUBMISSION. ' + subject

            result = self._template_send(
                subject, body, 'support@contentanalyticsinc.com', template_filename)

        if not result:
            raise SubmissionSpiderError('Email sending error')

        self.logger.info('Email was sent')

    def _template_export(self, caids, server_name):
        url = 'http://bulk-import.contentanalyticsinc.com/mc_export'

        data = {
            'retailer': 'samsclub_com',
            'server': server_name
        }

        files = {'file': ('caids.csv', 'CAID\n{}'.format('\n'.join(caids)))}

        response = requests.post(url, data=data, files=files).json()

        if response.get('error'):
            raise SubmissionSpiderError(response.get('message'))

        return response.get('file')

    def _template_name(self):
        name = 'items_{date}.xlsx'.format(
            date=datetime.now().strftime('%Y%m%d%H%M%S')
        )

        return name

    def _template_send(self, subject, body, to, template):
        msg = MIMEMultipart()

        msg['Subject'] = subject
        msg['From'] = 'retailer@contentanalyticsinc.com'
        msg['To'] = to

        msg.attach(MIMEText(body))

        attachment = MIMEApplication(open(template, 'rb').read())
        attachment.add_header('Content-Disposition', 'attachment', filename=os.path.split(template)[-1])
        msg.attach(attachment)

        try:
            ses = boto.connect_ses()

            ses.send_raw_email(msg.as_string(), source=msg['From'], destinations=[msg['To']])

            return True
        except:
            self.logger.error('Can not send email: {}'.format(traceback.format_exc()))
            return False

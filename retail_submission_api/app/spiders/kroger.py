from datetime import datetime
import time
import traceback
import zipfile
from urlparse import urljoin
from urlparse import urlparse

import boto
import requests
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from . import SubmissionSpider, SubmissionSpiderError


class KrogerSubmissionSpider(SubmissionSpider):
    retailer = 'kroger.com'

    domain = 'https://sft.kroger.com'

    def _export_template(self, products, server):
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

        url = 'http://bulk-import.contentanalyticsinc.com/mc_export'
        data = {
            'retailer': 'kroger_com',
            'server': server_name
        }
        files = {'file': ('caids.csv', 'CAID\n{}'.format('\n'.join(caids)))}
        response = requests.post(url, data=data, files=files).json()

        if response.get('error'):
            raise SubmissionSpiderError(response.get('message'))

        return response.get('file')

    def _send_email(self, sender, to, subject, body, cc=None):
        try:
            ses = boto.connect_ses()

            ses.send_email(
                source=sender,
                subject=subject,
                body=body,
                to_addresses=to,
                cc_addresses=cc
            )

            return True
        except:
            self.logger.error('Can not send email: {}'.format(traceback.format_exc()))
            return False

    def _submission_filename(self, options):
        filename = '{supplier}-{date}.zip'.format(
            supplier=options.get('supplier_name') or 'Files',
            date=datetime.now().strftime('%Y%m%d%H%M%S')
        )
        return filename

    def task_content(self, options, products, server, criteria, **kwargs):
        self.logger.info('Getting images')
        images = self._export_media(criteria, server)
        self.logger.info('Images: {}'.format(images))

        self.logger.info('Exporting template')
        filled_template_url = self._export_template(products, server)
        self.logger.info('Loading template: {}'.format(filled_template_url))
        filled_template = requests.get(filled_template_url).content

        self.logger.info('Creating submission file')
        submission_filename = self._submission_filename(options)
        submission = self.get_file_path_for_result(submission_filename)
        with zipfile.ZipFile(submission, 'w', compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(images, 'Images.zip')
            zip_file.writestr('Form.xlsx', filled_template)
        self.logger.info('Submission file: {}'.format(submission))

        self.login(options)

        try:
            self.logger.info('[Start upload images]')

            wait = WebDriverWait(self.driver, 20)

            self.logger.info('Click "File Manager"')
            self.driver.find_element_by_link_text('File Manager').click()
            wait.until(lambda driver: driver.find_element_by_xpath('//table[@id="files-gfc"]//a'))
            self.take_screenshot('After click')

            try:
                add_file = self.driver.find_element_by_link_text('Add File')
            except NoSuchElementException:
                self.logger.info('Click first workspace')
                self.driver.find_element_by_xpath('//table[@id="files-gfc"]//a').click()
                add_file = wait.until(lambda driver: driver.find_element_by_link_text('Add File'))
                self.take_screenshot('After click')

            self.logger.info('Click "Add File"')
            add_file.click()
            frame = wait.until(lambda driver: driver.find_element_by_id('iffile'))
            self.take_screenshot('After click')

            self.driver.switch_to.frame(frame)
            input_file = wait.until(lambda driver: driver.find_element_by_xpath('//*[@id="btnget"]//input'))
            self.driver.execute_script(
                "arguments[0].setAttribute('style','visibility: visible;');"
                "arguments[0].removeAttribute('multiple');",
                input_file
            )
            self.take_screenshot('File input was enabled')
            input_file.send_keys(submission)
            self.driver.switch_to.default_content()
            self.logger.info('Filled up form values')
            self.take_screenshot('Filled up form')

            if not self.sandbox and options.get('do_submit'):
                self.driver.find_element_by_id('btaddfile').click()
                wait = WebDriverWait(self.driver, 60)
                wait.until_not(lambda driver: driver.find_element_by_id('add-files'))
                self.take_screenshot('After send button clicked')
            else:
                self.logger.info('Uploaded, no click')

            self.logger.info('[End upload images]')
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

        self.logger.info('Sending email')

        sender = 'retailer@contentanalyticsinc.com'
        supplier = options.get('supplier_name')
        subject = 'Content Update' + (' for {supplier}'.format(supplier=supplier) if supplier else '')
        body = 'Hi Kroger Team,\nZip file {submission_filename} has been uploaded to the Kroger Secure File ' \
               'Transfer site https://sft.kroger.com/s/dhzs967jq. Could you please advice the process time? ' \
               'Thank you.'.format(submission_filename=submission_filename)

        if not self.sandbox and options.get('do_submit'):
            to = 'digital_item_setup@kroger.com'
        else:
            subject = 'TEST SUBMISSION. ' + subject
            to = 'support@contentanalyticsinc.com'

        result = self._send_email(sender, to, subject, body)

        if not result:
            raise SubmissionSpiderError('Email sending error')

        self.logger.info('Email was sent')

    def login(self, options):
        try:
            self.logger.info('[Start login]')

            auth_page = urljoin(self.domain, '/')
            self.logger.info('Loading auth page: {}'.format(auth_page))
            self.driver.get(auth_page)
            time.sleep(3)
            self.take_screenshot('Auth page')

            self.logger.info('Sending auth form')
            email = self.driver.find_element_by_name('g_username')
            password = self.driver.find_element_by_name('password')
            email.send_keys(options.get('email', ''))
            password.send_keys(options.get('password', ''))
            self.take_screenshot('Filled auth form')

            auth_form = self.driver.find_element_by_id('aform')
            auth_form.submit()
            time.sleep(6)
            self.take_screenshot('After submit of the auth form')

            if u'Unauthorized access' in self.driver.page_source \
                    or u'Invalid Username/Password' in self.driver.page_source:
                raise SubmissionSpiderError('Invalid email or password')

            self.logger.info('[End login]')
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Auth failed')
            self.logger.error('Auth error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Auth failed')

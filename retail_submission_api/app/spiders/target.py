import traceback
import boto
import shutil
import requests
import os
import time
import zipfile
import csv

from datetime import datetime
from urlparse import urlparse, urljoin
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from selenium.webdriver.support.ui import WebDriverWait

from . import SubmissionSpider, SubmissionSpiderError


class TargetSubmissionSpider(SubmissionSpider):
    retailer = 'target.com'

    domain = 'https://vendorpipeline.target.com'

    bucket_name = 'target-secureshare-submissions'

    security_questions = {
        'What was the name of your High School?': '414School',
        'What was your high school mascot?': '414Mascot',
        'In what city was your mother born?': '414City',
        'In what city was your high school?(full name of city only)': '414City',
        "What is your maternal grandmother's first name?": '414Name',
        "What is your best friend's first name?": '414Name',
        'What is the name of the first company you worked for?': '414Company',
        "What is your maternal grandfather's first name?": '414Name',
        'In what city were you married?(Enter full name of city)': '414Married',
        "What is your father's middle name?": '414Name',
        'What is the first name of the maid of honor at your wedding?': '414Wedding',
        'What is the first name of your oldest nephew?': '414Nephew',
        'What was the name of your first pet?': '414Pet',
        'In what city were you born?(Enter full name of city only)': '414City'
    }

    def _template_export(self, caids, server_name):
        url = 'http://bulk-import.contentanalyticsinc.com/mc_export'

        data = {
            'retailer': 'target_com',
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

    def _template_send(self, subject, body, to, cc, template):
        msg = MIMEMultipart()

        msg['Subject'] = subject
        msg['From'] = 'retailer@contentanalyticsinc.com'
        msg['To'] = to

        if cc:
            msg['Cc'] = ', '.join(cc)

        msg.attach(MIMEText(body))

        attachment = MIMEApplication(open(template, 'rb').read())
        attachment.add_header('Content-Disposition', 'attachment', filename=os.path.split(template)[-1])
        msg.attach(attachment)

        try:
            ses = boto.connect_ses()

            ses.send_raw_email(msg.as_string(), source=msg['From'], destinations=[msg['To']] + (cc if cc else []))

            return True
        except:
            self.logger.error('Can not send email: {}'.format(traceback.format_exc()))
            return False

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

        self.logger.info('Template saving')
        template_filename = self.get_file_path_for_result(self._template_name())
        response = requests.get(template_url, stream=True)

        with open(template_filename, 'wb') as template_file:
            shutil.copyfileobj(response.raw, template_file)

        self.logger.info('Template sending')

        supplier_name = options.get('supplier_name') or ''
        if supplier_name:
            supplier_name = 'for {} '.format(supplier_name)

        subject = 'Target Long Copy Form - Update content {supplier_name}{date}'.format(
            supplier_name=supplier_name,
            date=datetime.now().strftime('%Y-%m-%d')
        )

        body = 'Please update the long copy for the items in the attached file.'

        if not self.sandbox and options.get('do_submit'):
            result = self._template_send(
                subject, body, 'PC.Wrangler@target.com', options.get('additional_emails'), template_filename)
        else:
            subject = 'TEST SUBMISSION. ' + subject

            result = self._template_send(
                subject, body, 'support@contentanalyticsinc.com', None, template_filename)

        if not result:
            raise SubmissionSpiderError('Email sending error')

        self.logger.info('Email was sent')

    def task_images(self, options, products, server, criteria, **kwargs):
        images = self._export_media(criteria, server, options={
            'differences_only': options.get('differences_only', False),
            'image_type': options.get('image_type', 'jpg'),
            'image_resize': options.get('image_resize', False),
            'image_min_side_dimension': options.get('image_min_side_dimension', 1000)
        })

        self.logger.info('Sending images: {}'.format(images))

        self.login(options)

        try:
            self.logger.info('[START UPLOAD IMAGE]')

            input_file = self.driver.find_element_by_xpath('//body/label/input[@type="file"]')

            self.driver.execute_script(
                "arguments[0].parentNode.setAttribute('style','visibility: visible; position: relative');"
                "arguments[0].removeAttribute('multiple');",
                input_file
            )
            self.take_screenshot('File input was enabled')

            count = 0
            with zipfile.ZipFile(images, 'r') as zip_file:
                for image in zip_file.infolist():
                    image_filename = self.get_file_path_for_result(image.filename, append=False)

                    with open(image_filename, 'wb') as image_file:
                        shutil.copyfileobj(zip_file.open(image), image_file)

                    input_file.send_keys(image_filename)
                    count += 1

            wait = WebDriverWait(self.driver, 60)

            wait.until(
                lambda driver: driver.find_element_by_xpath(
                    '//ng-pluralize[@count="vm.validatedFiles.length"]').text.split()[0] == str(count)
            )

            self.take_screenshot('Files were attached')

            if not self.sandbox and options.get('do_submit'):
                self.driver.find_element_by_xpath(
                    './/*[@id="ft-send-to-target-btn" and @ng-click="vm.onUploadStart()"]').click()

                try:
                    wait.until_not(lambda driver: driver.find_element_by_xpath('//md-progress-circular'))
                except:
                    self.logger.warn('Files are submitting still')
                    self.take_screenshot('Files submitting')
                else:
                    self.take_screenshot('After send button clicked')
            else:
                self.logger.info('Uploaded, no click')

            self.logger.info('[END UPLOAD IMAGE]')
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

        products_filename = self.get_file_path_for_result('products.csv', append=None)
        with open(products_filename, 'wb') as products_file:
            products_csv = csv.writer(products_file)

            products_csv.writerow(['TCIN', 'Brand'])

            for product in products:
                brand = product.get('brand')

                if isinstance(brand, unicode):
                    brand = brand.encode('utf-8')

                products_csv.writerow([product.get('tcin'), brand])

        subject = 'Target media submission made for {server} - {date}'.format(
            server=self._get_server_name(server.get('url', '')),
            date=datetime.now().strftime('%Y-%m-%d')
        )

        if not self.sandbox and options.get('do_submit'):
            email = options.get('emails') or 'support@contentanalyticsinc.com'
        else:
            subject = 'TEST SUBMISSION. ' + subject
            email = 'support@contentanalyticsinc.com'

        body = "Hi Target Team,\n\n" \
               "We're working with the Content Analytics team to update our product content across our assortment " \
               "on Target.com. CAI has just submitted updated images to Pipeline for {} TCINs on our behalf.\n\n" \
               "Attached is a list of the TCINs for which we have submitted updated images. Can you please approve " \
               "these in Pipeline?\n\n" \
               "Let us know if you need any additional info from us to have these published on the site.\n\n" \
               "Thanks!".format(len(products))

        result = self._template_send(subject, body, email, None, products_filename)

        if not result:
            raise SubmissionSpiderError('Email sending error')

        self.logger.info('Email was sent')

    def login(self, options):
        try:
            self.logger.info('[START LOGIN]')

            auth_page = urljoin(self.domain, '/images/upload')
            self.logger.info('Loading auth page: {}'.format(auth_page))
            self.driver.get(auth_page)
            time.sleep(3)
            self.take_screenshot('Auth page')

            self.logger.info('Sending auth form')
            el_id = self.driver.find_element_by_name("username")
            el_pwd = self.driver.find_element_by_name("password")
            el_id.send_keys(options.get('username', ''))
            el_pwd.send_keys(options.get('password', ''))
            self.take_screenshot('Filled auth form')

            auth_form = self.driver.find_element_by_id("auth_form")
            auth_form.submit()

            wait = WebDriverWait(self.driver, 60)
            wait_method = lambda driver: driver.find_element_by_xpath(
                '//body/label/input[@type="file"]|'  # upload images
                '//*[@id="challengeForm"]|'  # security question
                '//*[@id="auth_form"]')  # login

            try:
                form = wait.until(wait_method)
            except:
                self.take_screenshot('Auth timeout')
                raise SubmissionSpiderError('Auth timeout')
            else:
                self.take_screenshot('After submit of the auth form')

            if form.get_attribute('id') == 'challengeForm':
                security_questions = options.get('security_questions') or self.security_questions
                for question, answer in security_questions.items():
                    question = question.split('?')[0].lower()
                    security_questions[question] = answer

                question = form.find_element_by_xpath('.//td[@class="BoldBody"]').text
                answer = security_questions.get(question.split('?')[0].lower())
                if not answer:
                    raise SubmissionSpiderError('No answer for security question: {}'.format(question))

                self.logger.info('Sending identity verification')
                el_ans = self.driver.find_element_by_name('userAnswer')
                el_ans.send_keys(answer)
                self.take_screenshot('Filled identity verification')
                form.submit()

                try:
                    form = wait.until(wait_method)
                except:
                    self.take_screenshot('Auth timeout')
                    raise SubmissionSpiderError('Auth timeout')
                else:
                    self.take_screenshot('After submit of identity verification')

                if form.get_attribute('id') in ('auth_form', 'challengeForm'):
                    raise SubmissionSpiderError('Wrong answer for security question: {}'.format(question))

            elif u'The username or password is not correct' in self.driver.page_source:
                raise SubmissionSpiderError('Invalid username or password')

            self.logger.info('[END LOGIN]')
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Auth failed')
            self.logger.error('Auth error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Auth failed')

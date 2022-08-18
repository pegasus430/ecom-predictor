from collections import defaultdict
import cStringIO
import json
import random
import string
import sys
import time
import traceback
import urllib2
import shutil
import csv
from datetime import datetime
from urlparse import urljoin
from lxml import etree

import xlrd
from PIL import Image
import pyotp
from pytesseract import image_to_string
import requests
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select, WebDriverWait
from xlutils.copy import copy

from . import SubmissionSpider, SubmissionSpiderError


class AmazonVcSubmissionSpider(SubmissionSpider):
    retailer = 'amazon.com'
    domain = 'https://vendorcentral.amazon.com'

    sandbox_address = '127.0.0.1:8889'
    bucket_name = 'vendor-central-submissions'

    captcha_max_tries = 15

    hpc_form_filename = 'Amazon-HPC-{counter}-Api-{date}({time}).xls'
    hpc_form_template_filename = 'HPC Template {num_of_bullets}.xls'
    hpc_form_template_folder = 'hpc'
    hpc_forms_counter = 0
    submisison_max_attachments = 4
    submisison_max_retries = 4

    def task_images(self, options, products, server, criteria, **kwargs):
        try:
            missing_options = {'primary', 'naming_conventions'} - set(options.keys())
            if missing_options:
                raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

            naming_conventions = options.get('naming_conventions', {})

            if not naming_conventions\
                    or not naming_conventions.get('configurable') and not naming_conventions.get('other'):
                raise SubmissionSpiderError('Naming conventions are empty')

            try:
                images = self._export_media(criteria, server, options={'naming_conventions': naming_conventions})
                exception = None
            except SubmissionSpiderError:
                images = False
                exception = sys.exc_info()

            self.logger.info('Sending images: {}'.format(images))

            self.login(options)

            self._check_images(products)

            if images:
                self._send_images(images, options)
            elif exception:
                raise exception[0], exception[1], exception[2]
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

    def _check_images(self, products):
        mc_images = defaultdict(set)
        for product in products:
            asin = product.get('asin')
            if asin:
                mc_images[asin].update(product.get('image_urls', []))

        if not mc_images:
            self.logger.error('No images to check')
            return

        amazon_images = {}
        for asin in mc_images:
            self.logger.info('Getting images for {}'.format(asin))
            retry_counter = 0
            while retry_counter < self.submisison_max_retries:
                try:
                    response = requests.get('http://chscraper.contentanalyticsinc.com/get_data?'
                                            'url=https://www.amazon.com/dp/' + asin)
                    response.raise_for_status()
                    data = response.json()
                    amazon_images[asin] = data.get('page_attributes', {}).get('image_urls', [])
                    break
                except:
                    self.logger.error('Cannot get images for {}: {}, response: {}'.format(
                        asin,
                        traceback.format_exc(),
                        response.content if response else ''
                    ))
                    retry_counter += 1
                    time.sleep(10 * retry_counter)
            else:
                raise SubmissionSpiderError('Cannot get images for {}'.format(asin))

        image_deletion = []
        for product_url in self._scrape_product_urls(mc_images):
            images = self._scrape_product_images(product_url)
            if not images:
                continue
            product_id = product_url.rsplit('=', 1)[-1]
            has_screenshot = False
            asin = images[0][0]
            for url in amazon_images[asin]:
                if url not in mc_images[asin]:
                    image_name = url.rsplit('/', 1)[-1]
                    image_deletion.append((product_url, url, image_name))
                    if has_screenshot:
                        continue
                    screenshot = Image.open(cStringIO.StringIO(self.driver.get_screenshot_as_png()))
                    live_images = self.driver.find_element_by_xpath('//div[@class="reconciled-images"]/div')
                    location = live_images.location
                    size = live_images.size
                    left = location['x']
                    top = location['y']
                    right = left + size['width']
                    bottom = top + size['height']
                    screenshot = screenshot.crop((left, top, right, bottom))
                    screenshot_name = self.get_file_path_for_result('{}.png'.format(product_id))
                    screenshot.save(screenshot_name)
                    has_screenshot = True
        if image_deletion:
            with open(self.get_file_path_for_result('Image_deletion.csv'), 'wb') as deletion_file:
                deletion_csv = csv.writer(deletion_file)
                deletion_csv.writerow(['product url', 'image url', 'image name'])
                deletion_csv.writerows(image_deletion)
        return image_deletion

    def _send_images(self, images, options):
        self.logger.info('[Start upload images]')

        try:
            self.logger.info('Click "Add images"')
            self.driver.find_element_by_link_text('Add images').click()
            time.sleep(3)
            self.take_screenshot('After click')

            upload = self.driver.find_element_by_name('Content')
            try:
                upload.clear()
            except:
                pass

            upload.send_keys(images)
            self.logger.info('Filled up form values')
            self.take_screenshot('Filled up form')

            if not options.get('do_submit'):
                self.logger.info('Uploaded, no click')
                self.logger.info('[End upload images]')

                return

            review_links_before = self.driver.find_elements_by_partial_link_text('Review the status')
            review_links_before = len(review_links_before) if review_links_before else 0

            self.logger.info('Submit the upload form')
            self.driver.find_element_by_id('submit').click()
            time.sleep(5)

            timeout = 120
            start_time = time.time()

            while time.time() - start_time < timeout:  # wait till there's submission status message
                review_links_after = self.driver.find_elements_by_partial_link_text('Review the status')
                review_links_after = len(review_links_after) if review_links_after else 0

                if review_links_after > review_links_before:
                    timeout = 0
                    break

                time.sleep(.5)

            self.take_screenshot('After form submit')
            if self.driver.current_url.split('&') and len(self.driver.current_url.split('&')[0].split('?')) > 1 \
                    and self.driver.current_url.split('&')[0].split('?')[1] == 'status=ok':
                self.logger.info('Images were uploaded successfully')
            else:
                if timeout:
                    self.logger.error('Submit button clicked, but submission failed by timeout')
                else:
                    self.logger.error('Failed to upload images')

                raise SubmissionSpiderError('Images submission failed')

            self.logger.info('[End upload images]')
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Images submission failed')
            self.logger.error('Images submission error: {}'.format(traceback.format_exc()))

            raise SubmissionSpiderError('Image submission failed')

    def task_text(self, options, products, **kwargs):
        try:
            missing_options = {'primary'} - set(options.keys())
            if missing_options:
                raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

            self.logger.info('Generating HPC forms')

            if options.get('submit_by_category'):
                products_by_category = self._sort_products_by_category(products)
            else:
                products_by_category = {'ALL': products}

            if options.get('submit_by_brand'):
                brand_groupings = self._get_brand_groupings(kwargs.get('server'))
            else:
                brand_groupings = None

            item_limit = options.get('item_limit', sys.maxint)
            try:
                item_limit = abs(int(item_limit))
            except:
                item_limit = 50

            tasks = []

            for category, category_products in products_by_category.iteritems():
                if brand_groupings is not None:
                    products_by_brand = self._sort_products_by_brand(category_products, brand_groupings)
                else:
                    products_by_brand = {'ALL': category_products}

                for brand, brand_products in products_by_brand.iteritems():
                    hpc_forms = self._generate_hpc_forms(brand_products,
                                                         item_limit=item_limit,
                                                         differences_only=options.get('differences_only'),
                                                         fields_only=options.get('fields_only'))

                    if hpc_forms:
                        max_attachments = 4

                        for i in range(0, len(hpc_forms), max_attachments):
                            tasks.append({
                                'hpc_forms': hpc_forms[i:i+max_attachments],
                                'brand': brand if brand != 'ALL' else None,
                                'group': category if category != 'ALL' else self._get_business_group(brand_products)
                            })

            self.logger.info('Sending HPC forms')

            self.login(options)

            for task in tasks:
                self._send_hpc_forms(task, options)
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

    def login(self, options):
        try:
            self.logger.info('[Start login]')

            auth_page = urljoin(self.domain, 'gp/vendor/sign-in?ie=UTF8')
            self.logger.info('Loading auth page: {}'.format(auth_page))
            self.driver.get(auth_page)
            time.sleep(2)
            self.take_screenshot('Auth page')

            self.logger.info('Pressing Sign In button')
            sign_in_button = self.driver.find_element_by_id("login-button-container")
            sign_in_button.click()
            time.sleep(5)
            self.take_screenshot('Auth form')

            self.logger.info('Sending auth form')
            username_el = self.driver.find_element_by_name("email")
            username_el.send_keys(options.get('primary', {}).get('email', ''))

            captcha_text = None

            for _ in range(self.captcha_max_tries):
                password_el = self.driver.find_element_by_name("password")
                password_el.send_keys(options.get('primary', {}).get('password', ''))

                if captcha_text:
                    self.logger.info("Sending captcha text '{}'".format(captcha_text))
                    captcha_el = self.driver.find_element_by_id('auth-captcha-guess')
                    captcha_el.send_keys(captcha_text)

                    submit_el = captcha_el
                else:
                    submit_el = self.driver.find_element_by_id("signInSubmit")

                self.take_screenshot('Filled auth form')
                submit_el.click()
                time.sleep(6)
                self.take_screenshot('After submit of the auth form')

                captcha_image = self._get_captcha()
                if not captcha_image:
                    break

                self.logger.debug(self.driver.current_url)
                self.logger.warn('Trying to solve captcha: {}'.format(captcha_image))
                captcha_text = self._solve_captcha(captcha_image)
            else:
                raise SubmissionSpiderError('Could not resolve the captcha')

            if u'We cannot find an account with that email address' in self.driver.page_source:
                raise SubmissionSpiderError('Invalid username')
            elif u'Your password is incorrect' in self.driver.page_source:
                raise SubmissionSpiderError('Invalid password')
            else:
                try:
                    # general case
                    raise SubmissionSpiderError(self.driver.find_element_by_id('auth-error-message-box').text)
                except NoSuchElementException:
                    # no errors
                    pass

            try:
                self.driver.find_element_by_name('otpCode')
            except NoSuchElementException:
                # skip 2-step verification setup
                try:
                    self.driver.get(urljoin(self.domain, '/hz/vendor/members/user-management/two-step-verification/interstitial-optional'))
                    wait = WebDriverWait(self.driver, 5)

                    remind_me_later = wait.until(
                        lambda driver: driver.find_element_by_link_text('Remind me later')
                    )
                    self.take_screenshot('2-step verification setup')

                    remind_me_later.click()
                    time.sleep(3)
                except:
                    pass
            else:
                secret_key = options.get('primary', {}).get('secret_key')
                if not secret_key:
                    raise SubmissionSpiderError('Secret key is required for accounts with Two-Step Verification')
                totp = pyotp.TOTP(secret_key.replace(' ', ''))
                for i in range(2):
                    self.logger.info('Sending Two-Step Verification form')
                    code_el = self.driver.find_element_by_name('otpCode')
                    code_el.send_keys(totp.now())

                    submit_el = self.driver.find_element_by_id("auth-signin-button")
                    self.take_screenshot('Filled Two-Step Verification form')
                    submit_el.click()
                    time.sleep(6)
                    self.take_screenshot('After submit of the Two-Step Verification form')

                    if u'The code you entered is not valid' not in self.driver.page_source:
                        break
                    elif not i:
                        self.logger.info('Two-Step Verification code could expire. Trying again')

                if u'The code you entered is not valid' in self.driver.page_source:
                    raise SubmissionSpiderError('Invalid secret key')
                else:
                    try:
                        # general case
                        raise SubmissionSpiderError(self.driver.find_element_by_id('auth-error-message-box').text)
                    except NoSuchElementException:
                        # no errors
                        pass

            dashboard_pages = map(lambda x: urljoin(self.domain, x), [
                '/st/vendor/members/dashboard',
                '/hz/vendor/members/home/ba'
            ])

            if self.driver.current_url not in dashboard_pages:
                # skip question
                self.logger.warn('Current url is not dashboard: {}. Trying to skip'.format(self.driver.current_url))
                self.driver.get(urljoin(self.domain, '/gp/vendor/members/dashboard'))
                time.sleep(3)

                if self.driver.current_url not in dashboard_pages:
                    self.logger.error('Current url is not dashboard: {}'.format(self.driver.current_url))
                    self.take_screenshot('Unknown landing page')
                    raise SubmissionSpiderError('Login successful, but not taken to Vendor Central home page')

                self.take_screenshot('Dashboard page')

            self.logger.info('Passed login form')
            self.logger.info('[End login]')
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Auth failed')
            self.logger.error('Auth error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Auth failed')

    def _get_captcha(self):
        try:
            return self.driver.find_element_by_id('auth-captcha-image').get_attribute('src')
        except NoSuchElementException:
            return None

    def _solve_captcha(self, image_url):
        image_text = ''.join(random.choice(string.ascii_lowercase) for _ in range(6))

        try:
            image_file = cStringIO.StringIO(urllib2.urlopen(image_url).read())
            img = Image.open(image_file)

            # TODO: solve more complex captcha, appears after simple captcha
            image_text = image_to_string(img).replace(' ', '').decode('utf-8') or image_text
        except:
            self.logger.error('Can not resolve captcha: {}'.format(traceback.format_exc()))

        return image_text

    def _sort_products_by_category(self, products):
        products_by_category = {}

        for product in products:
            category = product.get('category_name')

            products_by_category.setdefault(category, []).append(product)

        return products_by_category

    def _sort_products_by_brand(self, products, brand_groupings):
        products_by_brand = {}

        for product in products:
            brand = product.get('brand')

            for group, brands in brand_groupings.iteritems():
                if brand in brands:
                    brand = group
                    break

            products_by_brand.setdefault(brand, []).append(product)

        return products_by_brand

    def _generate_hpc_forms(self, products, item_limit=sys.maxint, differences_only=False, fields_only=[]):
        forms = []

        for i in range(0, len(products), item_limit):
            self.hpc_forms_counter += 1

            limit_products = products[i:i + item_limit]

            max_bullet_len = max(
                max(map(lambda x: len(x.get('bullets') if x.get('bullets') is not None else []), limit_products)),
                5)

            if max_bullet_len > 20:
                ids = [x.get('id') for x in limit_products
                       if len(x.get('bullets') if x.get('bullets') is not None else []) > 20]

                raise SubmissionSpiderError('Products ({}) have more than 20 bullets'.format(', '.join(ids)))

            template_name = self.hpc_form_template_filename.format(num_of_bullets=max_bullet_len)

            rb = xlrd.open_workbook('./{}/{}'.format(self.hpc_form_template_folder, template_name),
                                    formatting_info=True)
            wb = copy(rb)

            worksheet = wb.get_sheet(1)

            row_index = 5

            for product in limit_products:
                if differences_only:
                    differences = product.get('changedFields', {}).keys()
                    # skip product without changes
                    if not differences:
                        continue

                if fields_only:
                    self._set_out_cell(worksheet, 1, row_index, self._get_comment(fields_only))

                vendor_code_id = product['vendor_code_id']
                self._set_out_cell(worksheet, 2, row_index, vendor_code_id)

                sku_number = product['vendor_item_sku_number']
                self._set_out_cell(worksheet, 3, row_index, sku_number)

                asin = product['asin']
                self._set_out_cell(worksheet, 4, row_index, asin)

                brand_name = product['brand']
                if not differences_only and not fields_only\
                        or differences_only and 'brand' in differences\
                        or fields_only and 'brand' in fields_only:
                    self._set_out_cell(worksheet, 5, row_index, brand_name)

                item_name = product['product_name']
                if not differences_only and not fields_only\
                        or differences_only and 'product_name' in differences\
                        or fields_only and 'product_name' in fields_only:
                    self._set_out_cell(worksheet, 6, row_index, item_name)

                long_description = product['long_description']
                if not differences_only and not fields_only\
                        or differences_only and 'long_description' in differences\
                        or fields_only and 'long_description' in fields_only:
                    self._set_out_cell(worksheet, 30, row_index, long_description)

                browse_keywords = product['browse_keyword']
                if not differences_only and not fields_only\
                        or differences_only and 'browse_keyword' in differences\
                        or fields_only and 'browse_keyword' in fields_only:
                    self._set_out_cell(worksheet, 31 + max_bullet_len, row_index, browse_keywords)

                ingredients = product['ingredients']
                if not differences_only and not fields_only\
                        or differences_only and 'ingredients' in differences\
                        or fields_only and 'ingredients' in fields_only:
                    self._set_out_cell(worksheet, 32 + max_bullet_len, row_index, ingredients)

                directions = product['usage_directions']
                if not differences_only and not fields_only\
                        or differences_only and 'usage_directions' in differences\
                        or fields_only and 'usage_directions' in fields_only:
                    self._set_out_cell(worksheet, 33 + max_bullet_len, row_index, directions)

                safety_warnings = product['safety_warnings']
                if not differences_only and not fields_only\
                        or differences_only and 'safety_warnings' in differences\
                        or fields_only and 'safety_warnings' in fields_only:
                    self._set_out_cell(worksheet, 34 + max_bullet_len, row_index, safety_warnings)

                if product.get('bullets') is not None:
                    if not differences_only and not fields_only\
                            or differences_only and 'bullets' in differences\
                            or fields_only and 'bullets' in fields_only:
                        for bullet_index, bullet in enumerate(product['bullets'], start=1):
                            self._set_out_cell(worksheet, 30 + bullet_index, row_index, bullet)

                row_index += 1

            if row_index > 5:
                hpc_form_filename = self.hpc_form_filename.format(counter=self.hpc_forms_counter,
                                                                  date=datetime.now().strftime('%Y-%m-%d'),
                                                                  time=datetime.now().strftime('%H-%M-%S'))
                self.logger.debug('Generated HPC form: {}'.format(hpc_form_filename))

                hpc_form_path = self.get_file_path_for_result(hpc_form_filename)

                wb.save(hpc_form_path)

                forms.append(hpc_form_path)

        return forms

    def _get_out_cell(self, out_sheet, col_index, row_index):
        row = out_sheet._Worksheet__rows.get(row_index)

        if row:
            return row._Row__cells.get(col_index)

    def _set_out_cell(self, out_sheet, col, row, value):
        previous_cell = self._get_out_cell(out_sheet, col, row)

        out_sheet.write(row, col, value)

        if previous_cell:
            new_cell = self._get_out_cell(out_sheet, col, row)

            if new_cell:
                new_cell.xf_idx = previous_cell.xf_idx

    def _get_comment(self, fields):
        field_names = {
            'vendor_code_id': 'Vendor Code',
            'vendor_item_sku_number': 'Vendor Item',
            'asin': 'ASIN',
            'brand': 'Brand Name',
            'product_name': 'Item Name',
            'long_description': 'Product Description',
            'browse_keyword': 'Keywords',
            'ingredients': 'Ingredients',
            'usage_directions': 'Directions',
            'safety_warnings': 'Warnings',
            'bullets': 'Bullets'
        }

        # remove static fields from comment
        fields = [field for field in fields if field not in ('vendor_code_id', 'vendor_item_sku_number', 'asin')]

        if len(fields) == 1:
            return 'Only update {}'.format(field_names.get(fields[0], fields[0]))
        else:
            return 'Update {}'.format(', '.join(field_names.get(field, field) for field in fields))

    def _send_hpc_forms(self, task, options):
        retry_counter = 0

        self.logger.info('[Start upload text]')
        self.logger.info('Forms: {}'.format(task.get('hpc_forms')))

        try:
            wait = WebDriverWait(self.driver, 20)

            while retry_counter < self.submisison_max_retries:
                self.logger.info('Go to the contact page /hz/vendor/members/contact')

                self.driver.get(urljoin(self.domain, '/hz/vendor/members/contact'))
                time.sleep(4)

                self.take_screenshot('Contact page')

                group = task.get('group')

                if group:
                    try:
                        self.logger.info("Select Group '{}'".format(group))

                        business_group = Select(self.driver.find_element_by_id('businessGroupId'))
                        business_group.select_by_visible_text(group)
                    except:
                        try:
                            el = wait.until(
                                lambda driver: driver.find_element_by_xpath(
                                    '//*[@id="vss-contact-business-group-option-container"]'
                                    '//a[contains(text(), "{}")]'.format(group))
                            )
                            el.click()
                        except:
                            self.logger.error("Not found business group '{}'".format(group))
                        else:
                            time.sleep(3)
                            self.take_screenshot('After select group')
                    else:
                        time.sleep(3)
                        self.take_screenshot('After select group')
                else:
                    self.logger.info('No business group')

                try:
                    self.logger.info("Click 'Manage My Catalog'")

                    support_topic = Select(self.driver.find_element_by_id("issueId"))
                    support_topic.select_by_value("32600")
                except:
                    try:
                        el = wait.until(
                            lambda driver: driver.find_element_by_xpath(
                                '//span[contains(text(), "Manage My Catalog")]|'
                                '//*[contains(@id, "32600")]|'
                                '//*[contains(@id, "1000312")]')
                        )
                        el.click()
                    except:
                        retry_counter += 1

                        self.logger.error('Retry - an exception occured: {}'.format(traceback.format_exc()))

                        continue
                    else:
                        self.take_screenshot('After click')
                else:
                    self.take_screenshot('After click')

                try:
                    self.logger.info("Click 'Item Detail Page or Buy Button'")

                    specific_issue = Select(self.driver.find_element_by_id("subIssueId"))
                    specific_issue.select_by_value("32604")
                except:
                    try:
                        el = wait.until(
                            lambda driver: driver.find_element_by_xpath(
                                '//*[@aria-expanded="true"]//a[contains(text(), "Item Detail Page or Buy Button")]|'
                                '//*[contains(@id,"32604")]|'
                                '//*[@aria-expanded="true"]//a[contains(text(), "Item Detail Edit")]|'
                                '//*[contains(@id,"1000314")]')
                        )
                        el.click()
                    except:
                        self.logger.warn('No sub issue')
                    else:
                        self.take_screenshot('After click')
                else:
                    self.take_screenshot('After click')

                try:
                    self.logger.info("Click 'Send an email'")

                    self.driver.find_element_by_id("contactUsContinue").click()
                except:
                    try:
                        el = wait.until(
                            lambda driver: driver.find_element_by_link_text(
                                'Send an email')
                        )
                        el.click()
                    except:
                        self.logger.warn('No send an email link')

                try:
                    wait.until(
                        lambda driver: driver.find_element_by_id('subject')
                    )
                except:
                    self.take_screenshot('After click')

                    retry_counter += 1

                    self.logger.error('Retry - an exception occured: {}'.format(traceback.format_exc()))

                    continue

                break
            else:
                raise SubmissionSpiderError('Exceed form refresh limit')

            self.logger.info('Upload form is ready')
            self.take_screenshot('Upload form')

            self.logger.info('-Start form initialization-')

            title = self.driver.find_element_by_id('subject')

            brand = task.get('brand')
            if brand:
                date = datetime.now().strftime('%A, %B %d, %Y %I:%M %p')
                title.send_keys('Updated Copy for {brand} - {date}'.format(brand=brand, date=date))
            else:
                case_title = options.get('primary', {}).get('case_title') or ''
                if case_title:
                    case_title += ' - '

                date = datetime.now().strftime('%m-%d-%y')
                title.send_keys('{case_title}Please update product content for the attached items in the file ({date})'.
                                format(case_title=case_title, date=date))

            script = """
                jQuery('#subject').change();
            """
            self.driver.execute_script(script)

            self.logger.info("Set value on the 'subject' field")

            comments = "Hello Amazon team,\\n\\n" \
                       "Please update the ASINs listed in the attached Amazon Excel document for any product " \
                       "titles, descriptions, bullets, directions, ingredients and warnings, and browse keyword " \
                       "changes.\\n\\n" \
                       "Replace any existing content with the updated content provided. If any bullets exist " \
                       "in the spreadsheet for a product, please remove all existing bullets, and replace with only " \
                       "those in the spreadsheet.\\n\\n" \
                       "Update at the item and source level.\\n\\n" \
                       "Thank you!\\n"

            comments = options.get('comments') or comments

            self.logger.info('Set comments: {}'.format(comments))
            comments = comments.replace('\n', '\\n').replace('"', '\\"')

            script = """
            document.getElementById('vss-contact-email-cc-list-field-set-wrap').parentElement.style.display = 'block';
            var scAttachmentsWrapper = document.getElementsByClassName('vss-contact-attachment-content'),
             scAttachments = document.getElementsByClassName('vss-contact-attachment-file'),
            scIdx;
            for (scIdx = 0; scIdx < scAttachments.length; scIdx++) {{
                scAttachmentsWrapper[scIdx].style.display = 'block';
            }}
            for (scIdx = 0; scIdx < scAttachments.length; scIdx++) {{
                scAttachments[scIdx].className = 'vss-contact-attachment-file';
            }}
            document.getElementById('details').value="{comments}";
            jQuery('#details').change();
            """.format(comments=comments)
            self.driver.execute_script(script)

            self.logger.info("Set value on the 'Describe your issue' field")
            self.logger.info("The file fields and 'additional email addresses' fields are appeared")
            self.take_screenshot('Filling form')

            cc = self.driver.find_element_by_id("cc")
            cc.send_keys(options.get('emails', ''))
            self.logger.info('Set value on "additional email addresses" field')

            uploads = self.driver.find_elements_by_name('attachments')
            files = task.get('hpc_forms', [])

            for i, upload in enumerate(uploads):
                enable_field = """
                    var scAttachmentsWrapper = document.getElementsByClassName('vss-contact-attachment-content');
                    scAttachmentsWrapper[{}].style.display = 'block';
                """.format(i)
                self.driver.execute_script(enable_field)

                try:
                    upload.clear()
                except:
                    pass

                if i < len(files):
                    upload.send_keys(files[i])
                else:
                    break

            self.logger.info('Set file on the attachments field')

            self.logger.info('-Form initialization is finished.-')
            self.take_screenshot('Filled upload form')

            if not options.get('do_submit'):
                self.logger.info('Uploaded, no click')
                self.logger.info('[End upload text]')

                return

            try:
                self.driver.find_element_by_id('contactUsSubmit').click()
            except:
                try:
                    self.driver.find_element_by_xpath(
                        '//input[contains(@id, "contact-email-form")][contains(@id, "-submit")]').click()
                except:
                    self.logger.error('Submit button was not found')

                    raise SubmissionSpiderError('Submit button was not found')

            self.logger.info('Submit button was clicked.')

            time.sleep(3)

            self.take_screenshot('After submit click')

            # wait until file is uploaded : waiting time 20s
            start_time = time.time()

            while time.time() - start_time < 20:
                el_loader = self.driver.find_element_by_id('vss-contact-loading-mask')

                if not el_loader.is_displayed():
                    break
            else:
                self.logger.warn('Form is submitting still')
                self.take_screenshot('Form submitting')

            if not self.driver.find_element_by_id('vss-contact-email-confirmation-section').is_displayed():
                self.logger.info('Upload failure')
                self.logger.info('[End upload text]')

                raise SubmissionSpiderError('Upload failure')

            self.take_screenshot('Uploaded')

            self.logger.info('Uploaded')
            self.logger.info('[End upload text]')

            self._get_case_id()
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Text submission failed')
            self.logger.error('Text submission error: {}'.format(traceback.format_exc()))

            raise SubmissionSpiderError('Text submission failed')

    def _get_business_group(self, products):
        default_group = 'Beauty'

        groups = {default_group: 0}

        for product in products:
            group = product.get('category_name') or default_group

            groups[group] = groups.get(group, 0) + 1

        return max(groups, key=lambda x: groups[x])

    def _get_brand_groupings(self, server):
        missing_fields = {'url', 'api_key'} - set(server.keys())
        if missing_fields:
            self.logger.error('Missing mandatory server fields: {}'.format(', '.join(missing_fields)))
        else:
            url = '{server}/api/products/brands/brand_group?api_key={api_key}'.format(
                server=server['url'],
                api_key=server['api_key']
            )

            try:
                self.logger.debug('Loading brand groupings: {}'.format(url))
                res = urllib2.urlopen(url)
            except:
                self.logger.error('Can not load brand groupings from MC {}: {}'.format(url, traceback.format_exc()))
            else:
                if res.getcode() != 200:
                    self.logger.error('Can not load brand groupings from MC {}: response code {}, content: {}'.format(
                        url, res.getcode(), res.read()))
                else:
                    content = res.read()

                    try:
                        data = json.loads(content)

                        if data.get('status') == 'error':
                            self.logger.error('Can not load brand groupings from MC (error {}): {}'.format(
                                data.get('code'), data.get('message')))
                        else:
                            return dict(map(lambda g: (g['brand_group_name'].strip(),
                                                       map(lambda b: b.strip(), json.loads(g['brands']))),
                                            data.get('brands', [])))
                    except:
                        self.logger.error('Can not parse response from MC: {}'.format(content))

    def task_credentials_validation(self, options, **kwargs):
        try:
            missing_options = {'primary'} - set(options.keys())
            if missing_options:
                raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

            self.login(options)
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

    def _get_case_id(self):
        self.logger.info('[Start get Case ID]')
        try:
            self.logger.info('Go to open cases /gp/vendor/members/caselog/open-resolved')

            self.driver.get(urljoin(self.domain, '/gp/vendor/members/caselog/open-resolved'))
            self.take_screenshot('Open Cases')

            self.data['case_id'] = self.driver.find_element_by_id('Link_viewCase_1').text
        except:
            self.logger.error('Case ID was not found')
        finally:
            self.logger.info('[End get Case ID]')

    def task_remove_images(self, options, **kwargs):
        try:
            missing_options = {'primary', 'file', 'filename'} - set(options.keys())
            if missing_options:
                raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

            file_url = options['file']
            filename = options['filename']

            self.logger.info('Loading file {}: {}'.format(filename, file_url))
            stream = urllib2.urlopen(file_url)

            file_path = self.get_file_path_for_result(filename)

            with open(file_path, 'wb') as f:
                shutil.copyfileobj(stream, f)

            self.login(options)

            self._send_removed_images(file_path, options)
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

    def _send_removed_images(self, file_path, options):
        retry_counter = 0

        self.logger.info('[Start removing images]')
        self.logger.info('File: {}'.format(file_path))

        try:
            wait = WebDriverWait(self.driver, 20)

            while retry_counter < self.submisison_max_retries:
                self.logger.info('Go to the contact page /hz/vendor/members/contact')

                self.driver.get(urljoin(self.domain, '/hz/vendor/members/contact'))
                time.sleep(4)

                self.take_screenshot('Contact page')

                group = options.get('group')

                if group:
                    try:
                        self.logger.info("Select Group '{}'".format(group))

                        business_group = Select(self.driver.find_element_by_id('businessGroupId'))
                        business_group.select_by_visible_text(group)
                    except:
                        try:
                            el = wait.until(
                                lambda driver: driver.find_element_by_xpath('//a[contains(text(), "{}")]'.format(group))
                            )
                            el.click()
                        except:
                            self.logger.error("Not found business group '{}'".format(group))
                        else:
                            time.sleep(3)
                            self.take_screenshot('After select group')
                    else:
                        time.sleep(3)
                        self.take_screenshot('After select group')
                else:
                    try:
                        self.logger.info('Try to select first group')
                        el = wait.until(
                            lambda driver: driver.find_element_by_id('vss-contact-business-group-link-id-1')
                        )
                        el.click()
                    except:
                        self.logger.info('No business group')
                    else:
                        time.sleep(3)
                        self.take_screenshot('After select group')

                try:
                    self.logger.info("Click 'Images and Video'")

                    support_topic = Select(self.driver.find_element_by_id("issueId"))
                    support_topic.select_by_value("28467")
                except:
                    try:
                        el = wait.until(
                            lambda driver: driver.find_element_by_xpath(
                                '//span[contains(text(), "Images and Video")]|'
                                '//*[contains(@id, "28467")]|'
                                '//*[contains(@id, "1000254")]')
                        )
                        el.click()
                    except:
                        retry_counter += 1

                        self.logger.error('Retry - an exception occured: {}'.format(traceback.format_exc()))

                        continue
                    else:
                        self.take_screenshot('After click')
                else:
                    self.take_screenshot('After click')

                try:
                    self.logger.info("Click 'Image Troubleshoot'")

                    specific_issue = Select(self.driver.find_element_by_id("subIssueId"))
                    specific_issue.select_by_value("28361")
                except:
                    try:
                        el = wait.until(
                            lambda driver: driver.find_element_by_xpath(
                                '//a[contains(text(), "Image Troubleshoot")]|'
                                '//*[contains(@id,"28361")]|'
                                '//*[contains(@id,"1000514")]')
                        )
                        el.click()
                    except:
                        self.logger.warn('No sub issue')
                    else:
                        self.take_screenshot('After click')
                else:
                    self.take_screenshot('After click')

                try:
                    self.logger.info("Click 'Still need help?'")

                    el = wait.until(
                        lambda driver: driver.find_element_by_link_text(
                            'Still need help?')
                    )
                    el.click()
                except:
                    self.logger.warn("No still need help link")
                else:
                    self.take_screenshot('After click')

                try:
                    self.logger.info("Click 'Send an email'")

                    self.driver.find_element_by_id("contactUsContinue").click()
                except:
                    try:
                        el = wait.until(
                            lambda driver: driver.find_element_by_link_text(
                                'Send an email')
                        )
                        el.click()
                    except:
                        self.logger.warn('No send an email link')

                try:
                    wait.until(
                        lambda driver: driver.find_element_by_id('subject')
                    )
                except:
                    self.take_screenshot('After click')

                    retry_counter += 1

                    self.logger.error('Retry - an exception occured: {}'.format(traceback.format_exc()))

                    continue

                break
            else:
                raise SubmissionSpiderError('Exceed form refresh limit')

            self.logger.info('Upload form is ready')
            self.take_screenshot('Upload form')

            self.logger.info('-Start form initialization-')

            title = self.driver.find_element_by_id('subject')
            title.send_keys('Remove incorrect images for ASINs in the attached file')

            script = """
                jQuery('#subject').change();
            """
            self.driver.execute_script(script)

            self.logger.info("Set value on the 'subject' field")

            comments = "Please remove the incorrect images for all ASINs in the attached file. " \
                       "Details can be found there.\\n"

            comments = options.get('comments') or comments

            self.logger.info('Set comments: {}'.format(comments))
            comments = comments.replace('\n', '\\n').replace('"', '\\"')

            script = """
            document.getElementById('vss-contact-email-cc-list-field-set-wrap').parentElement.style.display = 'block';
            var scAttachmentsWrapper = document.getElementsByClassName('vss-contact-attachment-content'),
             scAttachments = document.getElementsByClassName('vss-contact-attachment-file'),
            scIdx;
            for (scIdx = 0; scIdx < scAttachments.length; scIdx++) {{
                scAttachmentsWrapper[scIdx].style.display = 'block';
            }}
            for (scIdx = 0; scIdx < scAttachments.length; scIdx++) {{
                scAttachments[scIdx].className = 'vss-contact-attachment-file';
            }}
            document.getElementById('details').value="{comments}";
            jQuery('#details').change();
            """.format(comments=comments)
            self.driver.execute_script(script)

            self.logger.info("Set value on the 'Describe your issue' field")
            self.logger.info("The file fields and 'additional email addresses' fields are appeared")
            self.take_screenshot('Filling form')

            cc = self.driver.find_element_by_id("cc")
            cc.send_keys(options.get('emails', ''))
            self.logger.info('Set value on "additional email addresses" field')

            uploads = self.driver.find_elements_by_name('attachments')
            files = [file_path]

            for i, upload in enumerate(uploads):
                enable_field = """
                    var scAttachmentsWrapper = document.getElementsByClassName('vss-contact-attachment-content');
                    scAttachmentsWrapper[{}].style.display = 'block';
                """.format(i)
                self.driver.execute_script(enable_field)

                try:
                    upload.clear()
                except:
                    pass

                if i < len(files):
                    upload.send_keys(files[i])
                else:
                    break

            self.logger.info('Set file on the attachments field')

            self.logger.info('-Form initialization is finished.-')
            self.take_screenshot('Filled upload form')

            if not options.get('do_submit'):
                self.logger.info('Uploaded, no click')
                self.logger.info('[End removing images]')

                return

            try:
                self.driver.find_element_by_id('contactUsSubmit').click()
            except:
                try:
                    self.driver.find_element_by_xpath(
                        '//input[contains(@id, "contact-email-form")][contains(@id, "-submit")]').click()
                except:
                    self.logger.error('Submit button was not found')

                    raise SubmissionSpiderError('Submit button was not found')

            self.logger.info('Submit button was clicked.')

            time.sleep(3)

            self.take_screenshot('After submit click')

            # wait until file is uploaded : waiting time 20s
            start_time = time.time()

            while time.time() - start_time < 20:
                el_loader = self.driver.find_element_by_id('vss-contact-loading-mask')

                if not el_loader.is_displayed():
                    break
            else:
                self.logger.warn('Form is submitting still')
                self.take_screenshot('Form submitting')

            if not self.driver.find_element_by_id('vss-contact-email-confirmation-section').is_displayed():
                self.logger.info('Upload failure')
                self.logger.info('[End removing images]')

                raise SubmissionSpiderError('Upload failure')

            self.take_screenshot('Uploaded')

            self.logger.info('Uploaded')
            self.logger.info('[End removing images]')

            self._get_case_id()
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Removing images failed')
            self.logger.error('Removing images error: {}'.format(traceback.format_exc()))

            raise SubmissionSpiderError('Removing images failed')

    def task_products(self, options, products, **kwargs):
        try:
            missing_options = {'primary'} - set(options.keys())
            if missing_options:
                raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

            self.login(options)

            if products:
                asins = [product['asin'] for product in products if product.get('asin')]
            else:
                asins = None

            product_urls = self._scrape_product_urls(asins)

            with open(self.get_file_path_for_result('products.csv'), 'wb') as products_file:
                products_csv = csv.writer(products_file)
                products_csv.writerows([product_url] for product_url in product_urls)
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

    def _scrape_product_urls(self, asins=None):
        self.logger.info('Scraping products')

        product_urls = []

        try:
            url = urljoin(self.domain, 'hz/vendor/members/products/mycatalog/ajax/query')

            while True:
                self.logger.info('Scraping products from url: {}'.format(url))
                self.driver.get(url)

                html = etree.HTML(self.driver.page_source)

                product_ids = html.xpath('.//input[@name="productId"]/@value')

                for product_id in product_ids:
                    if asins:
                        product_asin = product_id.split('-')[0]

                        if product_asin not in asins:
                            continue

                    product_urls.append('{}/hz/vendor/members/products/images/manage?'
                                        'products={}'.format(self.domain, product_id))

                next_url = html.xpath('.//li[@class="a-last"]/a/@href')

                if next_url:
                    url = urljoin(url, next_url[0])
                else:
                    break
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Products scraper failed')
            self.logger.error('Products scraper error: {}'.format(traceback.format_exc()))

            raise SubmissionSpiderError('Products scraper failed')

        return product_urls

    def task_images_info(self, options, products, **kwargs):
        try:
            missing_options = {'primary'} - set(options.keys())
            if missing_options:
                raise SubmissionSpiderError('Missing options: {}'.format(', '.join(missing_options)))

            self.login(options)

            if products:
                asins = {product['asin'] for product in products if product.get('asin')}
            else:
                asins = None

            product_urls = self._scrape_product_urls(asins)

            seen_urls = defaultdict(set)
            with open(self.get_file_path_for_result('images.csv'), 'wb') as images_file:
                images_csv = csv.writer(images_file)
                images_csv.writerow(['ASIN', 'UPC', 'Tag', 'url', 'alt'])
                for product_url in product_urls:
                    for asin, upc, tag, url, alt in self._scrape_product_images(product_url):
                        if url not in seen_urls[asin]:
                            images_csv.writerow([asin, upc, tag, url, alt])
                            seen_urls[asin].add(url)
        except SubmissionSpiderError:
            raise
        except:
            self.take_screenshot('Submission failed')
            self.logger.error('Submission error: {}'.format(traceback.format_exc()))
            raise SubmissionSpiderError('Submission failed')

    def _scrape_product_images(self, product_url):
        self.logger.info('Scraping images from url: {}'.format(product_url))

        rows = []

        retry_counter = 0
        while retry_counter < self.submisison_max_retries:

            self.logger.info('Loading page')
            self.driver.get(product_url)

            self.logger.info('Waiting for images block')
            try:
                WebDriverWait(self.driver, 3).until(
                    lambda driver: driver.find_element_by_xpath('//div[@class="images"]'))
            except TimeoutException:
                self.logger.warn('Timeout while waiting for images block')
                retry_counter += 1
                continue

            self.logger.info('Waiting for images loaded')
            try:
                WebDriverWait(self.driver, 20).until_not(
                    lambda driver: driver.find_element_by_xpath('//div[@class="loading-spinner"]'))
            except TimeoutException:
                self.logger.warn('Timeout while waiting for images loaded')
                retry_counter += 1
                continue

            self.logger.info('Loaded')

            asin = self.driver.find_element_by_xpath(
                '//li[@data-asin]').get_attribute('data-asin') or ''
            asin = asin.strip()
            try:
                upc = self.driver.find_element_by_xpath(
                    '//li[@data-external-id-type="UPC"]').get_attribute(
                    'data-external-id-value') or ''
                upc = upc.strip()
            except NoSuchElementException:
                try:
                    upc = self.driver.find_element_by_xpath(
                        '//li[@data-external-id-type="GTIN"]').get_attribute(
                        'data-external-id-value') or ''
                    upc = upc.strip()[-12:]
                except NoSuchElementException:
                    upc = ''

            images = self.driver.find_element_by_xpath(
                '//div[@class="reconciled-images"]//div[@class="images"]')
            for variant in images.find_elements_by_xpath('./div'):
                tag = variant.find_element_by_xpath('.//span[@class="image-variant-label"]').text.strip()
                try:
                    image = variant.find_element_by_xpath('.//div[@class="modal-image"]//img')
                except NoSuchElementException:
                    image = variant.find_element_by_xpath('.//div[@class="image-box"]//img')
                url = image.get_attribute('src') or ''
                alt = image.get_attribute('alt') or ''
                rows.append([asin, upc, tag, url, alt])

            break
        else:
            raise SubmissionSpiderError('Cannot load images from url: {}'.format(product_url))

        return rows


class AmazonFreshSubmissionSpider(AmazonVcSubmissionSpider):
    retailer = 'amazon fresh'


class AmazonPantrySubmissionSpider(AmazonVcSubmissionSpider):
    retailer = 'amazon pantry'


class AmazonPrimenowSubmissionSpider(AmazonVcSubmissionSpider):
    retailer = 'amazon primenow'

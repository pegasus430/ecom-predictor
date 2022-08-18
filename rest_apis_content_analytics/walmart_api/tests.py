# -*- coding: utf-8 -*-

import os
import time
import sys
import json

from django.test import TestCase, Client
from django.contrib.auth.models import AnonymousUser, User
import requests
import lxml.html

CWD = os.path.dirname(os.path.abspath(__file__))


from django.test import LiveServerTestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.conf import settings
from selenium import webdriver
from selenium.common.exceptions import TimeoutException


class RestAPIsTests(StaticLiveServerTestCase):

    reset_sequences = True

    xml_file1 = os.path.join(CWD, 'walmart_product_xml_samples', 'SupplierProductFeed.xsd.xml')
    xml_file2 = os.path.join(CWD, 'walmart_product_xml_samples', 'Verified Furniture Sample Product XML.xml')
    xml_file3 = os.path.join(CWD, 'walmart_product_xml_samples', 'Invalid verified furniture sample product xml.xml')

    @classmethod
    def setUpClass(cls):
        super(RestAPIsTests, cls).setUpClass()
        cls.selenium = webdriver.Chrome()
        cls.selenium.set_window_size(1280, 1024)
        with open(settings.TEST_TWEAKS['item_upload_ajax_ignore'], 'w') as fh:
            fh.write('1')

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(RestAPIsTests, cls).tearDownClass()
        if os.path.exists(settings.TEST_TWEAKS['item_upload_ajax_ignore']):
            os.remove(settings.TEST_TWEAKS['item_upload_ajax_ignore'])

    def setUp(self):
        # create user
        self.username = 'admin4'
        self.email = 'admin@admin.com'
        self.password = 'admin46'
        if not User.objects.filter(username=self.username):
            self.user = User.objects.create_superuser(self.username, self.email, self.password)
        else:
            self.user = User.objects.filter(username=self.username)[0]

    def tearDown(self):
        self.user.delete()

    def _auth(self):
        #self.selenium.get(self.live_server_url+'/admin/')
        self.selenium.get(self.live_server_url+'/api-auth/login/')
        self.selenium.find_element_by_name('username').send_keys(self.username)
        self.selenium.find_element_by_name('password').send_keys(self.password + '\n')
        time.sleep(1)  # let the database commit transactions?

    def _http_auth(self, url):
        self.selenium.set_page_load_timeout(4)
        try:
            self.selenium.get(url)
        except:
            self.selenium.set_page_load_timeout(30)
            self.selenium.get('http://'+self.username+':'+self.password+'@'+url.replace('http://', ''))
            return

    def _auth_requests(self):
        session = requests.Session()
        session.auth = (self.username, self.password)
        return session

    def test_login(self):
        self._auth()
        self.assertIn(settings.LOGIN_REDIRECT_URL, self.selenium.current_url)
        self.assertTrue(self.selenium.get_cookie('sessionid'))

    def _test_validate_walmart_product_xml_file_browser(self, xml_file):
        self._auth()
        self.selenium.get(self.live_server_url+'/validate_walmart_product_xml_file/')
        self.selenium.find_element_by_name('xml_file_to_validate').send_keys(xml_file)
        self.selenium.find_element_by_xpath('//*[contains(@class, "form-actions")]/button').click()
        self.assertIn('success', self.selenium.page_source)
        self.assertIn('is validated by Walmart product xsd files', self.selenium.page_source)

    def _test_validate_walmart_product_xml_file_requests(self, xml_file):
        session = self._auth_requests()
        with open(xml_file, 'rb') as payload:
            result = session.post(self.live_server_url+'/validate_walmart_product_xml_file/',
                                  files={'xml_file_to_validate': payload}, verify=False)
            self.assertIn('success', result.text)
            self.assertIn('is validated by Walmart product xsd files', result.text)

    def _test_validate_walmart_product_xml_file_requests_multiple(self, *xml_files):
        session = self._auth_requests()
        xml_files_opened = [open(f, 'rb') for f in xml_files]
        files2post = {'file_'+str(i): f for (i, f) in enumerate(xml_files_opened)}
        result = session.post(self.live_server_url+'/validate_walmart_product_xml_file/',
                              files=files2post, verify=False)
        result_json = json.loads(result.text)
        self.assertIn('success', str(result_json['Verified Furniture Sample Product XML.xml']))
        self.assertIn('error', result_json['SupplierProductFeed.xsd.xml'])

    def test_validate_walmart_product_xml_file(self):
        self._test_validate_walmart_product_xml_file_browser(self.xml_file2)
        self._test_validate_walmart_product_xml_file_requests(self.xml_file2)
        self._test_validate_walmart_product_xml_file_requests_multiple(self.xml_file1, self.xml_file2)

    def test_items_update_with_xml_file_by_walmart_api(self):
        request_url_pattern = 'request_url'
        request_method_pattern = 'request_method'
        xml_file_to_upload_pattern = 'xml_file_to_upload'
        payload = {
            request_url_pattern: 'https://marketplace.walmartapis.com/v2/feeds?feedType=item',
            request_method_pattern: 'POST',
            request_url_pattern+'_2': 'https://marketplace.walmartapis.com/v2/feeds?feedType=item',
            request_method_pattern+'_2': 'POST',
        }
        files = {
            xml_file_to_upload_pattern: open(self.xml_file1, 'rb'),
            xml_file_to_upload_pattern+'_2': open(self.xml_file2, 'rb')
        }
        session = self._auth_requests()
        result = session.post(self.live_server_url+'/items_update_with_xml_file_by_walmart_api/',
                              data=payload, files=files, verify=False)
        result_json = json.loads(result.text)
        self.assertEqual(result_json.get('default', {}).get('error', ''), 'could not find <productId> element')
        self.assertIn('feedId', result_json.get('_2', ''))

    def test_detect_duplicate_content(self):
        # TODO: better test coverage
        # now we only check that this view works for both authenticated and non-authenticated users (in browser)
        self.selenium.delete_all_cookies()  # "logout"
        self._http_auth(self.live_server_url+'/detect_duplicate_content/')
        self.selenium.get(self.live_server_url+'/detect_duplicate_content/')
        self.assertTrue(bool(self.selenium.find_element_by_xpath('//h1[contains(text(), "Detect Duplicate Content")]')))
        self._auth()
        self.selenium.get(self.live_server_url+'/detect_duplicate_content/')
        self.assertTrue(bool(self.selenium.find_element_by_xpath('//h1[contains(text(), "Detect Duplicate Content")]')))

    def test_statistics(self):
        # TODO: the code below is WRONG! fix it
        """
        self.test_items_update_with_xml_file_by_walmart_api()
        self.selenium.delete_all_cookies()  # "logout"
        # remove ajax blocker
        if os.path.exists(settings.TEST_TWEAKS['item_upload_ajax_ignore']):
            os.remove(settings.TEST_TWEAKS['item_upload_ajax_ignore'])
        self.selenium.set_page_load_timeout(2)
        try:
            self._auth()
            self.selenium.get(self.live_server_url+'/items_update_with_xml_file_by_walmart_api/')
        except TimeoutException:
            pass  # sometimes it takes too long to process all requests
        self.selenium.set_page_load_timeout(30)
        import pdb; pdb.set_trace()
        self.assertEqual(self.selenium.find_element_by_id('stat_counter_today').text, '1 / 1')
        self.assertEqual(self.selenium.find_element_by_id('stat_counter_all_time').text, '1')
        self.assertEqual(self.selenium.find_element_by_id('stat_counter_success').text, '1')
        # put ajax blocker back
        # remove ajax blocker
        with open(settings.TEST_TWEAKS['item_upload_ajax_ignore'], 'w') as fh:
            fh.write('1')
        """

    def test_compare_images_lists(self):
        test_data = {
            "urls1": [
                 "http://i5.walmartimages.com/dfw/dce07b8c-2899/k2-_3d73fbf9-014b-48a8-be67-e7379814f7c1.v4.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-58e1/k2-_318bc7df-78ee-47ba-b7dc-1b56114edbb6.v1.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-b0c7/k2-_78ec4336-3b56-4a4d-98ac-8d448728aed9.v1.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-da62/k2-_e540b841-5121-45f2-9202-41690eabd6a0.v1.jpg"],
            "urls2": [
                 "http://i5.walmartimages.com/dfw/dce07b8c-70a9/k2-_ca865772-2e81-4e32-a1e9-98d8c0bf3742.v1.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-3614/k2-_d9c29d82-0790-4515-8d69-f6e25b64c156.v1.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-b1ea/k2-_74ec32ac-829f-4afd-ba77-d0863e53ca2d.v1.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-4803/k2-_19057378-6e9e-469c-8baf-4b36a950d43e.v1.jpg",
                 "http://i5.walmartimages.com/dfw/dce07b8c-8986/k2-_26616eae-e118-4787-8a51-0a28a9783b5b.v1.jpg"
            ]
        }
        self._auth()
        self.selenium.get(self.live_server_url+'/comparetwoimagelists/')
        self.selenium.find_element_by_link_text('Raw data').click()
        self.selenium.find_element_by_id('id__content').send_keys(json.dumps(test_data, indent=4))
        self.selenium.execute_script("window.scrollBy(0,8000)", "")
        for button in self.selenium.find_elements_by_css_selector('form .form-actions button.btn-primary'):
            try:
                button.click()
            except:
                continue
        self.assertInHTML("""
<pre class="prettyprint"><span class="meta nocode"><b>HTTP 200 OK</b>
<b>Allow:</b> <span class="lit">GET, POST, HEAD, OPTIONS</span>
<b>Content-Type:</b> <span class="lit">application/json</span>
<b>Vary:</b> <span class="lit">Accept</span>

</span><span class="pun">{</span><span class="pln">
    </span><span class="str">"</span><a href="http://i5.walmartimages.com/dfw/dce07b8c-58e1/k2-_318bc7df-78ee-47ba-b7dc-1b56114edbb6.v1.jpg" rel="nofollow"><span class="str">http://i5.walmartimages.com/dfw/dce07b8c-58e1/k2-_318bc7df-78ee-47ba-b7dc-1b56114edbb6.v1.jpg</span></a><span class="str">"</span><span class="pun">:</span><span class="pln"> </span><span class="kwd">null</span><span class="pun">,</span><span class="pln">
    </span><span class="str">"</span><a href="http://i5.walmartimages.com/dfw/dce07b8c-b0c7/k2-_78ec4336-3b56-4a4d-98ac-8d448728aed9.v1.jpg" rel="nofollow"><span class="str">http://i5.walmartimages.com/dfw/dce07b8c-b0c7/k2-_78ec4336-3b56-4a4d-98ac-8d448728aed9.v1.jpg</span></a><span class="str">"</span><span class="pun">:</span><span class="pln"> </span><span class="kwd">null</span><span class="pun">,</span><span class="pln">
    </span><span class="str">"</span><a href="http://i5.walmartimages.com/dfw/dce07b8c-2899/k2-_3d73fbf9-014b-48a8-be67-e7379814f7c1.v4.jpg" rel="nofollow"><span class="str">http://i5.walmartimages.com/dfw/dce07b8c-2899/k2-_3d73fbf9-014b-48a8-be67-e7379814f7c1.v4.jpg</span></a><span class="str">"</span><span class="pun">:</span><span class="pln"> </span><span class="kwd">null</span><span class="pun">,</span><span class="pln">
    </span><span class="str">"</span><a href="http://i5.walmartimages.com/dfw/dce07b8c-da62/k2-_e540b841-5121-45f2-9202-41690eabd6a0.v1.jpg" rel="nofollow"><span class="str">http://i5.walmartimages.com/dfw/dce07b8c-da62/k2-_e540b841-5121-45f2-9202-41690eabd6a0.v1.jpg</span></a><span class="str">"</span><span class="pun">:</span><span class="pln"> </span><span class="kwd">null</span><span class="pln">
</span><span class="pun">}</span></pre>
        """, self.selenium.page_source, 1)

    def test_compare_images(self):
        self._auth()

        # 1
        self.selenium.get(self.live_server_url+'/comparetwoimages/')
        self.selenium.find_element_by_link_text('Raw data').click()
        self.selenium.execute_script("window.scrollBy(0,8000)", "")
        for button in self.selenium.find_elements_by_css_selector('form .form-actions button.btn-primary'):
            try:
                button.click()
            except:
                continue
        self.assertInHTML("""
<div class="response-info">
              <pre class="prettyprint"><span class="meta nocode"><b>HTTP 400 Bad Request</b>
<b>Allow:</b> <span class="lit">GET, POST, HEAD, OPTIONS</span>
<b>Content-Type:</b> <span class="lit">application/json</span>
<b>Vary:</b> <span class="lit">Accept</span>

</span><span class="pun">{</span><span class="pln">
    </span><span class="str">"detail"</span><span class="pun">:</span><span class="pln"> </span><span class="str">"JSON parse error - No JSON object could be decoded"</span><span class="pln">
</span><span class="pun">}</span></pre>
            </div>
        """, self.selenium.page_source, 1)

        # 2
        test_data = {
            "urls": [
                "http://i5.wal.co/dfw/dce07b8c-8883/k2-_c66baaae-8379-4337-b420-d10fe5b67308.v1.jpg",
                "http://i5.wal.co/dfw/dce07b8c-8883/k2-_c66baaae-8379-4337-b420-d10fe5b67308.v1.jpg"
            ]
        }
        self.selenium.get(self.live_server_url+'/comparetwoimages/')
        self.selenium.find_element_by_link_text('Raw data').click()
        self.selenium.find_element_by_id('id__content').send_keys(json.dumps(test_data, indent=4))
        self.selenium.execute_script("window.scrollBy(0,8000)", "")
        for button in self.selenium.find_elements_by_css_selector('form .form-actions button.btn-primary'):
            try:
                button.click()
            except:
                continue
        self.assertInHTML("""
<div class="response-info">
              <pre class="prettyprint"><span class="meta nocode"><b>HTTP 200 OK</b>
<b>Allow:</b> <span class="lit">GET, POST, HEAD, OPTIONS</span>
<b>Content-Type:</b> <span class="lit">application/json</span>
<b>Vary:</b> <span class="lit">Accept</span>

</span><span class="pun">{</span><span class="pln">
    </span><span class="str">"Are two images similar?"</span><span class="pun">:</span><span class="pln"> </span><span class="str">"Yes"</span><span class="pln">
</span><span class="pun">}</span></pre>
            </div>
        """, self.selenium.page_source, 1)

    def test_check_item_status_by_product_id(self):
        self._auth()
        self.selenium.get(self.live_server_url+'/check_item_status_by_product_id/')
        self.selenium.find_element_by_name('numbers').send_keys('123456, 56854\n5216 6545')
        self.selenium.execute_script("window.scrollBy(0,8000)", "")
        for button in self.selenium.find_elements_by_css_selector('form .form-actions button.btn-primary'):
            try:
                button.click()
            except:
                continue
        self.assertInHTML("""
<div class="response-info">
              <pre class="prettyprint"><span class="meta nocode"><b>HTTP 200 OK</b>
<b>Allow:</b> <span class="lit">GET, POST, HEAD, OPTIONS</span>
<b>Content-Type:</b> <span class="lit">application/json</span>
<b>Vary:</b> <span class="lit">Accept</span>

</span><span class="pun">{</span><span class="pln">
    </span><span class="str">"5216"</span><span class="pun">:</span><span class="pln"> </span><span class="str">"NOT FOUND"</span><span class="pun">,</span><span class="pln">
    </span><span class="str">"6545"</span><span class="pun">:</span><span class="pln"> </span><span class="str">"NOT FOUND"</span><span class="pun">,</span><span class="pln">
    </span><span class="str">"123456"</span><span class="pun">:</span><span class="pln"> </span><span class="str">"NOT FOUND"</span><span class="pun">,</span><span class="pln">
    </span><span class="str">"56854"</span><span class="pun">:</span><span class="pln"> </span><span class="str">"NOT FOUND"</span><span class="pln">
</span><span class="pun">}</span></pre>
            </div>
        """, self.selenium.page_source, 1)
        self.assertInHTML(u"""
<div id="content2">
          <div class="well">
            <div id="content2_table"><table class="table stats_table" id="item_status_table"><tbody><tr><th class="sortable" style="cursor: pointer;">Code<span class="table_up_arrow" style="display: none;"> ↑</span><span class="table_down_arrow" style="display: none;"> ↓</span></th><th class="sortable" style="cursor: pointer;">Feed ID<span class="table_up_arrow" style="display: none;"> ↑</span><span class="table_down_arrow" style="display: none;"> ↓</span></th><th class="sortable" style="cursor: pointer;">Date/Time Submitted<span class="table_up_arrow" style="display: none;"> ↑</span><span class="table_down_arrow" style="display: inline;"> ↓</span></th><th class="sortable" style="cursor: pointer;">Status<span class="table_up_arrow" style="display: none;"> ↑</span><span class="table_down_arrow" style="display: none;"> ↓</span></th></tr><tr><td>123456</td><td colspan="3">NOT FOUND</td></tr><tr><td>56854</td><td colspan="3">NOT FOUND</td></tr><tr><td>6545</td><td colspan="3">NOT FOUND</td></tr><tr><td>5216</td><td colspan="3">NOT FOUND</td></tr></tbody></table></div>
          </div>
          <script>
              function insertAfter(newNode, referenceNode) {
                  referenceNode.parentNode.insertBefore(newNode, referenceNode.nextSibling);
              }
              function drawCheckItemStatusTable(data) {
                  var table = '<table class="table stats_table" id="item_status_table">';
                  table += '<tr><th class="sortable">Code</th><th class="sortable">Feed ID</th>';
                  table += '<th class="sortable">Date/Time Submitted</th><th class="sortable">Status</th></tr>';
                  for(var number in data) {
                      var top_value = data[number];
                      if (top_value == 'NOT FOUND') table += '<tr><td>' + number.toString() + '</td><td colspan="3">NOT FOUND</td></tr>';
                      else {
                          for(var subm_date in top_value) {
                              var value = top_value[subm_date];
                              table += '<tr>';
                              table += '<td>' + number.toString() + '</td>';
                              table += '<td>' + value.feed_id.toString() + '</td>';
                              table += '<td>' + value.datetime.toString() + '</td>';
                              table += '<td>' + value.status.toString() + '</td>';
                              table += '</tr>';
                          }
                      }
                      //table += '<tr><td colspan="4" style="border: 0"></td></tr>';
                  }
                  return table;
              }
              var raw_content = {
    "5216": "NOT FOUND",
    "6545": "NOT FOUND",
    "123456": "NOT FOUND",
    "56854": "NOT FOUND"
};
          </script>
      </div>
      """, self.selenium.page_source, 1)

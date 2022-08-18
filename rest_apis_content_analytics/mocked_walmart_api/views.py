import binascii
import datetime
import os
import os.path
import pytz
import random
import re
import xmltodict
import string

from django.conf import settings
from rest_framework.response import Response

from models import MockedXMLStatus
from statistics.models import process_check_feed_response

from walmart_api.views import (CheckFeedStatusByWalmartApiViewSet,
                               ItemsUpdateWithXmlFileByWalmartApiViewSet,
                               validate_walmart_product_xml_against_xsd,
                               get_client_ip, get_walmart_api_invoke_log,
                               FeedStatusAjaxView)

from walmart_api.models import (SubmissionHistory, SubmissionXMLFile,
                                SubmissionStatus)

def get_feed_status(user, feed_id, date=None, process_check_feed=True, check_auth=True,
                    server_name=None, client_ip=None):

    if os.path.exists(settings.TEST_TWEAKS['item_upload_ajax_ignore']):
        # do not perform time-consuming operations - return dummy empty response
        return {}
    if check_auth and not user.is_authenticated():
        return

    # try to get data from cache
    feed_history = SubmissionHistory.objects.filter(user=user,
                                                    feed_id=feed_id)
    if feed_history:
        return {
            'statuses': feed_history[0].get_statuses(),
            'ok': feed_history[0].all_items_ok(),
            'partial_success': feed_history[0].partial_success(),
            'in_progress': feed_history[0].in_progress()
        }
    # if no cache found - perform real check, update stats, and save cache
    feed_checker = MockedCheckFeedStatusByWalmartApiViewSet()
    check_results = feed_checker.process_one_set("", feed_id)

    if process_check_feed and date:
        process_check_feed_response(user, check_results,
                                    date=date, check_auth=check_auth)

    ingestion_statuses = check_results.get(
        'itemDetails', {}).get('itemIngestionStatus', [])

    print "Generating feed Status"

    print "ingestion_statuses"
    for result_stat in ingestion_statuses:
        print result_stat
        subm_stat = result_stat.get('ingestionStatus', None)
        print subm_stat
        if subm_stat and isinstance(subm_stat, (str, unicode)):
            db_history = SubmissionHistory.objects.create(
                user=user, feed_id=feed_id,
                server_name=server_name, client_ip=client_ip)
            db_history.set_statuses([subm_stat])

    if not ingestion_statuses:
        print "Not ingestion_statuses"
        if check_results.get('feedStatus', '').lower() == 'error':
            print "Error"
            db_history = SubmissionHistory.objects.create(
                user=user, feed_id=feed_id,
                server_name=server_name, client_ip=client_ip)
            db_history.set_statuses(['error'])

    feed_history = SubmissionHistory.objects.filter(user=user,
                                                    feed_id=feed_id)

    if feed_history:
        return {
            'statuses': feed_history[0].get_statuses(),
            'ok': feed_history[0].all_items_ok(),
            'partial_success': feed_history[0].partial_success(),
            'in_progress': feed_history[0].in_progress()
        }
    return {}


class MockedItemsUpdateWithXmlFileByWalmartApiViewSet(ItemsUpdateWithXmlFileByWalmartApiViewSet):

    # Called from Create -> HTTP POST
    def process_one_set(self, request, sent_file, request_url, request_method,
                        do_not_validate_xml=False, multi_item=False):

        with open(os.path.dirname(os.path.realpath(__file__)) + "/upload_file.xml", "wb") as upload_file:
            xml_data_by_list = sent_file.read()
            xml_data_by_list = xml_data_by_list.splitlines()

            for xml_row in xml_data_by_list:
                upload_file.write((xml_row + "\n").decode("utf-8").encode("utf-8"))

        upload_file = open(os.path.dirname(os.path.realpath(__file__)) + "/upload_file.xml", "rb")
        product_xml_text = upload_file.read()

        # create stat report
        upc = re.findall(r'<productId>(.*)</productId>', product_xml_text)
        if not upc:
            return {'error': 'could not find <productId> element'}
        upc = upc[0]

        # we don't use validation against XSD because it fails - instead,
        #  we assume we have checked each sub-product already
        validation_results = 'okay'
        if not do_not_validate_xml:
            validation_results = validate_walmart_product_xml_against_xsd(product_xml_text)

        if "error" in validation_results:
            return validation_results

        rand_feed = binascii.b2a_hex(os.urandom(16))
        feed_id = "%s-%s-%s-%s-%s" % (rand_feed[0:8], rand_feed[8:12], rand_feed[12:16], rand_feed[16:20], rand_feed[20:])    

        current_time = datetime.datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()  # always show TZ

        server_name = request.POST.get('server_name')
        client_ip = get_client_ip(request)

        # save uploaded XML file right away
        self._save_uploaded_xml_file(feed_id, upload_file)
        response = {}
        response['feedId'] = feed_id
        # save log
        with open(get_walmart_api_invoke_log(request), "a+") as myfile:
            myfile.write(current_time + ", " + upc + ", " + server_name +
                         ", " + client_ip + ", " + feed_id + "\n")

        with open(get_walmart_api_invoke_log(request), "a+") as myfile:
            response["log"] = myfile.read().splitlines()

        if isinstance(response['log'], list):
            response['log'].reverse()

            pagination = self._paginate_log_file_results(request, response['log'])
            pagination['log'] = pagination.pop('paginated_list')

            for key, value in pagination.items():
                response[key] = value

        # create SubmissionHistory and Stats right away
        get_feed_status(request.user, feed_id, date=datetime.datetime.now(),
                        server_name=server_name, client_ip=client_ip)

        return response


def generate_sucess_fails(p, process):
    if p < 0.50:
        success = process
        errors = 0

    elif p < 0.80:
        success = random.randint(int(process / 2), process)
        errors = process - success
    else:
        success = 0
        errors = process

    return success, errors

class MockedCheckFeedStatusByWalmartApiViewSet(CheckFeedStatusByWalmartApiViewSet):

    # Get
    def list(self, request):
        return Response({'data': 'OK'})

    # Post
    def process_one_set(self, request_url, request_feed_id):
        try:
            subm_hist = MockedXMLStatus.objects.get(feed_id=request_feed_id)
        except MockedXMLStatus.DoesNotExist:
            subm_hist = None

        time_now = datetime.datetime.now()

        try:
            file = SubmissionXMLFile.objects.get(feed_id=request_feed_id)
        except SubmissionXMLFile.DoesNotExist:
                return {"Error": "Feed ID not found"}

        file_content = file.xml_file.read()
        supplier_xml = xmltodict.parse(file_content)
        items = supplier_xml['SupplierProductFeed']['SupplierProduct']

        if not isinstance(items, list):
            items = [items]

        response = {}
        response = {'itemDetails': {}}
        response['itemDetails']['offset'] = 0
        response['itemDetails']['limit'] = 50
        # TO DO: change it for real value
        num_items = len(items)

        values = {'feed_id': request_feed_id,
                  'current_status': "INPROGRESS",
                  'in_progress': num_items,
                  'success': 0,
                  'errors': 0,
                  'data_error': 0,
                  'timeout_error': 0}

        if subm_hist:
            # Based on the time since creation, we can guess its status 
            seconds_since_submit = ((time_now.replace(tzinfo=None) -
                                     file.created.replace(tzinfo=None)).total_seconds())

            # This way the same feed id file will display similar content
            random.seed(file_content)

            print "seconds_since_submit: %d" % seconds_since_submit

            if seconds_since_submit < 30:
                # Too Few time --> Still waiting
                values['current_status'] = "INPROGRESS"
                values['in_progress'] = subm_hist.in_progress
                values['success'] = subm_hist.success
                values['errors'] = subm_hist.errors
                values['data_error'] = subm_hist.data_error
                values['timeout_error'] = subm_hist.timeout_error

            elif seconds_since_submit < 60:
                # First Time Checking In progress, generate random values
                values['current_status'] = "INPROGRESS"
                if subm_hist.in_progress == num_items:
                    process = random.randint(0, num_items - 1)

                    p = random.random()
                    success, errors = generate_sucess_fails(p, process)

                    values['in_progress'] = subm_hist.in_progress = (num_items - process)
                    values['success'] = subm_hist.success = success
                    values['errors'] = subm_hist.errors = errors
                    values['data_error'] = subm_hist.data_error = random.randint(0, errors)
                    values['timeout_error'] = subm_hist.timeout_error = (errors - subm_hist.data_error)
                    subm_hist.save()

                # We have previously checked this status, copy old values
                else:
                    values['in_progress'] = subm_hist.in_progress
                    values['success'] = subm_hist.success
                    values['errors'] = subm_hist.errors
                    values['data_error'] = subm_hist.data_error
                    values['timeout_error'] = subm_hist.timeout_error

            else:
                if subm_hist.in_progress == num_items:
                    values['in_progress'] = subm_hist.in_progress = 0

                    p = random.random()
                    success, errors = generate_sucess_fails(p, num_items)

                    values['success'] = subm_hist.success = success
                    values['errors'] = subm_hist.errors = errors
                    values['data_error'] = subm_hist.data_error = random.randint(0, subm_hist.errors)
                    values['timeout_error'] = subm_hist.timeout_error = subm_hist.errors - subm_hist.data_error

                elif subm_hist.current_status == "INPROGRESS":
                    values['success'] = subm_hist.success = subm_hist.success + subm_hist.in_progress
                    values['in_progress'] = subm_hist.in_progress = 0
                    values['errors'] = subm_hist.errors
                    values['data_error'] = subm_hist.data_error
                    values['timeout_error'] = subm_hist.timeout_error

                elif subm_hist.current_status == "PROCESSED":
                    values['in_progress'] = subm_hist.in_progress
                    values['success'] = subm_hist.success
                    values['errors'] = subm_hist.errors
                    values['data_error'] = subm_hist.data_error
                    values['timeout_error'] = subm_hist.timeout_error

                subm_hist.current_status = "PROCESSED"
                values['current_status'] = "PROCESSED"

            subm_hist.save()

        # First time Checked
        else:
            values['in_progress'] = num_items
            MockedXMLStatus(**values).save()

        response['itemsReceived'] = (values['success'] +
                                     values['data_error'] +
                                     values['timeout_error'])

        response['itemsProcessing'] = values['in_progress']
        response['itemDetails']['itemsFailed'] = (values['data_error'] +
                                                  values['timeout_error'])
        response['itemDetails']['itemsSucceeded'] = values['success']
        response['itemDetails']['ingestionErrors'] = {"ingestionError": None}
        response['itemDetails']['feedStatus'] = values['current_status']
        response['itemDetails']['feedId'] = "%s" % (request_feed_id)

        del values['feed_id']
        del values['errors']
        del values['current_status']

        response['itemDetails']['itemIngestionStatus'] = self.generate_items(
            items, **values)

        if subm_hist:
            histories = SubmissionHistory.objects.filter(feed_id=request_feed_id)
            for index, history in enumerate(histories):
                try:
                    submissions = SubmissionStatus.objects.filter(history=history.id)
                    for submission in submissions:
                        submission.delete()
                except:
                    import traceback
                    print traceback.print_exc()
                new_status = response['itemDetails']['itemIngestionStatus'][index]['ingestionStatus']
                history.set_statuses([new_status])

        response['feed_id'] = request_feed_id
        return response

    def generate_items(self, items, in_progress, success, data_error, timeout_error):
        results = []
        i = 0
        for (j, item) in enumerate(items):
            r = {}
            r["index"] = (1 + j)
            r["sku"] = item['productIdentifiers']['productIdentifier']['productId']
            random.seed(str(item))
            r["wpid"] = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12))
            r["martId"] = 0
            results.append(r)

        start = 0
        for i in range(in_progress):
            r = results[start + i]
            r["ingestionStatus"] = "INPROGRESS"
            r["ingestionErrors"] = {"ingestionError": None}
        start += in_progress

        for i in range(success):
            r = results[start + i]
            r["ingestionStatus"] = "SUCCESS"
            r["ingestionErrors"] = {"ingestionError": None}
        start += success

        for i in range(data_error):
            r = results[start + i]
            r["ingestionStatus"] = "DATA_ERROR"
            error = {}
            error["type"] = "DATA_ERROR"
            error["code"] = "ERR_PDI_0005"
            error["description"] = ("Unexpected system error occurred in product data"
                                    " setup. Please contact Walmart.com support.")
            r["ingestionErrors"] = {"ingestionError": [error]}

        start += data_error
        for i in range(timeout_error):
            r = results[start + i]
            r["ingestionStatus"] = "TIMEOUT_ERROR"
            r["ingestionErrors"] = {"ingestionError": None}

        return results


class MockedFeedStatusAjaxView(FeedStatusAjaxView):
    def get(self, request, *args, **kwargs):
        feed_id = kwargs['feed_id']
        # If last time it was IN Progress, try to update values
        try:
            subm_hist = MockedXMLStatus.objects.get(feed_id=feed_id)
            if subm_hist.current_status == "INPROGRESS":
                mockedCheckFeedStatus = MockedCheckFeedStatusByWalmartApiViewSet()
                mockedCheckFeedStatus.process_one_set("", feed_id)
        except:
            pass

        return super(MockedFeedStatusAjaxView, self).get(request, *args, **kwargs)
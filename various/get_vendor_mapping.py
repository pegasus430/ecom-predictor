import requests
import json
import sys
import traceback
import logging


logger = logging.getLogger(__name__)


def setup_logger(log_level=logging.DEBUG):
    """
    Setup logger formats and handlers

    :param log_level: logging level
    :return:
    """

    logger.setLevel(logging.DEBUG)

    log_format = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
    log_format.datefmt = '%Y-%m-%d %H:%M:%S'

    log_stdout = logging.StreamHandler()
    log_stdout.setFormatter(log_format)
    log_stdout.setLevel(log_level)
    logger.addHandler(log_stdout)


def get_vendors(tcin_list=None):
    # GET VENDOR ID FROM TCIN
    url = "https://api.target.com/digital_items/v1/lite"
    key = "bd932758273956ab88284963312c677c42e394ad"
    headers = {
        'authorization': "Bearer DbLz0cQ1TrTZkSYpl0nc8NojXIZEmRQi",
        'content-type': "application/json",
        'cache-control': "no-cache"
    }
    results = {}

    tcin_request_limit = 100
    for i in range(0, len(tcin_list), tcin_request_limit):
        sub_tcin_list = tcin_list[i:i + tcin_request_limit]

        tcin = ','.join([str(x).strip() for x in sub_tcin_list])

        querystring = {"tcins": tcin, "key": key}

        try:
            response = requests.request("GET", url, headers=headers, params=querystring)

            if response.status_code in [200, 206]:
                json_response = json.loads(response.text)
                for items in json_response:
                    results[items['tcin']] = {}
                    tcin_obj = results[items['tcin']]

                    tcin_obj['brand'] = items.get('product_brand', {}).get('brand', '')

                    # CHECK IF PRIMARY VENDOR
                    primary_vendor = get_primary_vendor(items.get('product_vendors', None))
                    tcin_obj['vendor_id'], tcin_obj['vendor'] = primary_vendor if primary_vendor else ('', '')

                    tcin_obj['code'] = items.get('relationship_type_code', '')
                    if tcin_obj['code'] == 'COP':
                        # IF relationship_type_code is 'COP', this means that it is a Collection item,
                        # which doesn't have a Vendor Associated to it.
                        tcin_obj['vendor_id'] = ''
                    elif tcin_obj['code'] in ('VAP', 'VPC'):
                        # If VAP or VPC is present and no vendor ID/Name is provided, use vendor of first child
                        if not tcin_obj['vendor_id']:
                            try:
                                child_items = items['child_items']
                                querystring = {"tcins": child_items[0]['tcin'], "key": key}
                                response = requests.request("GET", url, headers=headers, params=querystring)
                                response = json.loads(response.text)
                                primary_vendor = get_primary_vendor(response[0].get('product_vendors', None))
                                tcin_obj['vendor_id'], tcin_obj['vendor'] = primary_vendor if primary_vendor else (
                                '', '')
                            except:
                                logger.error("Exception for tcins {}: {}".format(tcin, traceback.format_exc()))

                    tcin_obj['status'] = items.get('estore_item_status', '')
            else:
                logger.error("Error response received for:" + tcin)
                logger.error("Error code: " + str(response.status_code))

        except:
            logger.error("Exception for tcins {}: {}".format(tcin, traceback.format_exc()))

    noresponse_tcin_list = [x for x in tcin_list if x not in results.keys()]
    if noresponse_tcin_list:
        logger.error("Invalid TCINs in request. No response received for :" + ', '.join(map(str, noresponse_tcin_list)))

    return results


def get_primary_vendor(vendor_list):
    if not vendor_list:
        return None
    for vendor in vendor_list:
        # Check for primary vendor, and return primary vendor id
        if vendor.get('is_primary_vendor'):
            return vendor.get('id', ''), vendor.get('vendor_name', '')

    # If no primary vendor is present, return first vendor id
    return vendor_list[0].get('id', ''), vendor_list[0].get('vendor_name', '')


if __name__ == '__main__':
    setup_logger(100)  # 100 means stop logging

    if len(sys.argv) > 1 and sys.argv[2] == 'Relationship':
        try:
            # list_of_tcin = [52324323,50700752,21466848,51914515,50183918,50684960,51122448]
            list_of_tcin = json.JSONDecoder().decode(sys.argv[1])
        except:
            logger.error('Can not parse TCINs: {}'.format(traceback.format_exc()))
        else:
            response_received = get_vendors(list_of_tcin)
            print response_received

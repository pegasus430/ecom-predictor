import re
import yaml
import json
import lxml.html
import traceback
import itertools


class WalmartVariants(object):

    def setupSC(self, response):
        """ Call it from SC spiders """
        self.response = response
        self.tree_html = lxml.html.fromstring(response.body)

    def setupCH(self, tree_html):
        """ Call it from CH spiders """
        self.tree_html = tree_html

    def _clean_text(self, text):
        text = text.replace("<br />"," ").replace("\n"," ").replace("\t"," ").replace("\r"," ")
        text = re.sub("&nbsp;", " ", text).strip()
        return  re.sub(r'\s+', ' ', text)

    def _variants(self):
        version = 'Walmart v1'
        if self.tree_html.xpath("//meta[@name='keywords']/@content"):
            version = "Walmart v2"
        if self.tree_html.xpath("//meta[@name='Keywords']/@content"):
            version = "Walmart v1"

        if version == "Walmart v1":
            try:
                script_raw_text = " " . join(self.tree_html.xpath("//script/text()"))

                start_index = script_raw_text.find("var variants = ") + len("var variants = ")
                end_index = script_raw_text.find(";\nvar variantWidgets = [", start_index)
                variants_json = script_raw_text[start_index:end_index]
                variant_item_list = []
                start_index = end_index = 0

                while True:
                    start_index = variants_json.find("{\nitemId:", end_index)
                    end_index = variants_json.find(",\n{\nitemId:", start_index)

                    if end_index < 0:
                        end_index = variants_json.rfind("]")
                        variant_item_list.append(variants_json[start_index:end_index])
                        break

                    variant_item_list.append(variants_json[start_index:end_index])

                variant_list = []

                for item in variant_item_list:
                    variant_item = {}

                    start_index = item.find("attributeData:") + len("attributeData:")
                    end_index = item.find(",\nstoreItemData:", start_index)
                    variant_item_json = item[start_index:end_index]
                    variant_item_json = variant_item_json.replace(":'", ": '")
                    variant_item_json = yaml.load(variant_item_json)

                    properties = {}

                    for property in variant_item_json:
                        property_name = property["variantAttrName"].lower()
                        property_value = property["variantAttrValue"]
                        properties[property_name] = property_value

                    start_index = item.find("itemId:") + len("itemId:")
                    end_index = item.find(",", start_index)
                    item_id = item[start_index:end_index].strip()
                    original_product_canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]
                    if not re.match("https?://www.walmart.com", original_product_canonical_link):
                        original_product_canonical_link = "http://www.walmart.com" + original_product_canonical_link
                    variant_product_url = original_product_canonical_link[:original_product_canonical_link.rfind("/") + 1] + str(item_id)

                    start_index = item.find("isInStock:") + len("isInStock:")
                    end_index = item.find(",", start_index)
                    stock_status = (item[start_index:end_index].strip().lower() == 'true')

                    start_index = item.find("currentItemPrice:") + len("currentItemPrice:")
                    end_index = item.find(",", start_index)
                    price = float(item[start_index:end_index].strip())

                    variant_item["properties"] = properties
                    variant_item["in_stock"] = stock_status
                    variant_item["url"] = variant_product_url
                    variant_item["price"] = price
                    variant_item["selected"] = False

                    variant_list.append(variant_item)

                if not variant_list:
                    return None

                return variant_list
            except:
                print "Walmart v1 variant passing issue"
                return None

        if version == "Walmart v2":
            try:
                if getattr(self, 'response', None):
                    # SC spiders sometimes fail to perform correct conversion
                    # response.body -> lxml.html tree -> tostring
                    page_raw_text = self.response.body
                else:
                    page_raw_text = lxml.html.tostring(self.tree_html)

                startIndex = page_raw_text.find('"variantTypes":') + len('"variantTypes":')

                if startIndex == -1:
                    return None

                endIndex = page_raw_text.find(',"variantProducts":', startIndex)

                json_text = page_raw_text[startIndex:endIndex]
                json_body = json.loads(json_text)

                variation_key_values_by_attributes = {}
                variation_key_unav_by_attributes = {}

                attribute_values_list = []

                for variation_attribute in json_body:

                    variation_key_values = {}
                    variation_key_unav = {}
                    variation_attribute_id = variation_attribute["id"]

                    if "variants" in variation_attribute:
                        for variation in variation_attribute["variants"]:
                            variation_key_values[variation["id"]] = variation["name"]
                            variation_key_unav[variation["id"]] = (variation['status'] == 'not available')

                    variation_key_values_by_attributes[variation_attribute_id] = variation_key_values
                    variation_key_unav_by_attributes[variation_attribute_id] = variation_key_unav

                for variation_key in variation_key_values_by_attributes:
                    attribute_values_list.append(variation_key_values_by_attributes[variation_key].values())

                out_of_stock_combination_list = list(itertools.product(*attribute_values_list))
                out_of_stock_combination_list = [list(tup) for tup in out_of_stock_combination_list]

                selected_variants = {}

                for item in json_body:

                    if "variants" in item:
                        if "selectedValue" not in item:
                            selected_variants = None
                            break

                        selected_variants[item["id"]] = item["selectedValue"]

                startIndex = page_raw_text.find('"variantProducts":') + len('"variantProducts":')

                if startIndex == -1:
                    return None

                endIndex = page_raw_text.find(',"primaryProductId":', startIndex)

                json_text = page_raw_text[startIndex:endIndex]

                color_size_stockstatus_json_body = json.loads(json_text)
                stockstatus_for_variants_list = []

                original_product_canonical_link = self.tree_html.xpath("//link[@rel='canonical']/@href")[0]

                if not re.match("https?://www.walmart.com", original_product_canonical_link):
                    original_product_canonical_link = "http://www.walmart.com" + original_product_canonical_link

                for item in color_size_stockstatus_json_body:
                    variants = item["variants"]
                    stockstatus_for_variants = {}
                    properties = {}
                    isSelected = True
                    variant_values_list = []

                    for key in variants:
                        if key in variation_key_values_by_attributes:
                            if variants[key]["id"] not in variation_key_values_by_attributes[key].keys():
                                continue

                            if key == "actual_color":
                                properties["color"] = variation_key_values_by_attributes[key][variants[key]["id"]]
                            else:
                                properties[key] = variation_key_values_by_attributes[key][variants[key]["id"]]

                            variant_values_list.append(variation_key_values_by_attributes[key][variants[key]["id"]])

                            if selected_variants and selected_variants[key] != variation_key_values_by_attributes[key][variants[key]["id"]]:
                                isSelected = False

                    if variant_values_list in out_of_stock_combination_list:
                        out_of_stock_combination_list.remove(variant_values_list)
                    else:
                        continue

                    if not selected_variants:
                        isSelected = False

                    try:
                        variant_product_id = item['buyingOptions']['usItemId']
                        variant_product_url = original_product_canonical_link[:original_product_canonical_link.rfind("/") + 1] + str(variant_product_id)
                        stockstatus_for_variants["url"] = variant_product_url
                        if item['buyingOptions'].get('offerId'):
                            stockstatus_for_variants["in_stock"] = item['buyingOptions']['available']
                        else:
                            stockstatus_for_variants["in_stock"] = False
                    except Exception, e:
                        stockstatus_for_variants["url"] = None
                        stockstatus_for_variants["in_stock"] = False

                    stockstatus_for_variants["properties"] = properties
                    stockstatus_for_variants["price"] = None
                    stockstatus_for_variants["selected"] = isSelected
                    stockstatus_for_variants_list.append(stockstatus_for_variants)

                for item in out_of_stock_combination_list:
                    stockstatus_for_variants = {}
                    properties = {}

                    for index, key in enumerate(variation_key_values_by_attributes):
                        if key == "actual_color":
                            properties["color"] = item[index]
                        else:
                            properties[key] = item[index]

                    stockstatus_for_variants["url"] = None
                    stockstatus_for_variants["in_stock"] = False
                    stockstatus_for_variants["properties"] = properties
                    stockstatus_for_variants["price"] = None
                    stockstatus_for_variants["selected"] = False
                    stockstatus_for_variants["unavailable"] = True
                    stockstatus_for_variants_list.append(stockstatus_for_variants)

                if not stockstatus_for_variants_list:
                    return None
                else:
                    return stockstatus_for_variants_list
            except:

                print "Walmart v2 variant passing issue"
                return None

        return None

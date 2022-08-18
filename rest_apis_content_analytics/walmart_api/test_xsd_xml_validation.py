__author__ = 'root'

import os
from lxml import etree

current_path = os.path.dirname(os.path.realpath(__file__))

xmlschema_doc = etree.parse(current_path + "/walmart_suppliers_product_xsd/SupplierProductFeed.xsd")
xmlschema = etree.XMLSchema(xmlschema_doc)
xmlparser = etree.XMLParser(schema=xmlschema)

doc = etree.parse(current_path + "/walmart_product_xml_samples/Verified Furniture Sample Product XML.xml")
valid_result = xmlschema.validate(doc)
print valid_result

try:
    with open(current_path + "/walmart_product_xml_samples/Verified Furniture Sample Product XML.xml", 'r') as f:
        etree.fromstring(f.read(), xmlparser)
except Exception, e:
    print e


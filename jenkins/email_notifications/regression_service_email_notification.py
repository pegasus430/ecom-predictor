import os
import smtplib
from os.path import basename
import json
import psycopg2
import psycopg2.extras
import sys
import time
import csv
import gzip
import shutil
from datetime import date, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate

AMAZON_SES_KEY = os.getenv('AMAZON_SES_KEY', '')
AMAZON_SES_SECRET = os.getenv('AMAZON_SES_SECRET', '')

import boto

con = None
con = psycopg2.connect(database='scraper_test', user='root', password='QdYoAAIMV46Kg2qB', host='scraper-test.cmuq9py90auz.us-east-1.rds.amazonaws.com', port='5432')
cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)

today = date.today()

fromaddr = "jenkins@contentanalyticsinc.com"
toaddrs = ["qa@contentanalyticsinc.com"]  # must be a list
subject = "Regression Service Summary Report: {0}".format(today.isoformat())
msg = MIMEMultipart(
        From=fromaddr,
        To=COMMASPACE.join(toaddrs),
        Date=formatdate(localtime=True)
        )
msg['Subject'] = subject
msg.preamble = subject
header_content = "Possibly Changed Sites:\n"
sites_changed = ""
email_content = "\nWeb console:\nhttp://regression.contentanalyticsinc.com:8080/regression/\nlogin: tester\npassword: password\n\n"
newdatahtml = ""
websites = ["walmart", "jcpenney", "kohls", "macys", "target", "levi", "dockers", "samsclub", "drugstore", "amazon"]
categories = ["Total tested product numbers:", "Not a product count:", "Product numbers of content structure changed:", "Product numbers of version changed:", "Percentage of changed products:", "80 percent of product titles are < 2 characters long:", "80 percent of review counts are 0:", "80 percent of product descriptions are < 2 words long:", "80 percent of image counts are 0:", "80 percent of products are out of stock:", "Possibility of overall website changes:"]
keys = ["totaltested", "notaproduct", "structurechanged", "versionchanged", "changedproducts", "titles", "reviewcounts", "descriptions", "imagecounts", "outofstock", "possibilitychanges"]
cathtml = ""
for c in categories:
    cathtml += "<p>%s</p>" % c
day1 = []
day2 = []
day3 = []
day4 = []
html = '<table border="1"><tr><th></th>'
for website in websites:
    html += "<th>%s</th>" % website
    sql = "SELECT * FROM email_history WHERE website = \'%s\' ORDER BY day ASC" % website
    cur.execute(sql)
    rows = cur.fetchall()
    day1.append(rows[0])
    day2.append(rows[1])
    day3.append(rows[2])
    day4.append(rows[3])
for k in keys:
    sql = "UPDATE email_history t2 SET {0} = t1.{0} FROM email_history t1 WHERE t2.day = t1.day+1 and t2.website = t1.website".format(k)
    cur.execute(sql)

for website in websites:
    if website == "amazon":
        sql_sample_products = "select id, url, website, json, not_a_product from console_urlsample where website like '{0}'".format("amazon%")
    else:
        sql_sample_products = "select id, url, website, json, not_a_product from console_urlsample where website='{0}'".format(website)

    cur.execute(sql_sample_products)
    rows = cur.fetchall()

    invalid_products_list = []
    upc_missing_product_list = []
    review_issue_product_list = []
    price_issue_product_list = []
    marketplace_issue_product_list = []
    walmart_v1_product_list = []

    number_of_reported_products = len(rows)
    number_of_not_a_product = 0
    #> 80% of product titles are < 2 characters long
    count_product_titles_are_less_than_2_character_long = 0
    #> 80% of review counts are 0
    count_review_counts_are_0 = 0
    #> 80% of product descriptions are < 2 words long
    count_product_descriptions_are_less_than_2_character_long = 0
    #> 80% of image counts are 0
    count_image_counts_are_0 = 0
    #> 80% of products are out of stock
    count_products_are_out_of_stock = 0

    for row in rows:
        try:
            sample_json = json.loads(row["json"])
            number_of_not_a_product += int(row["not_a_product"])
            if "sellers" not in sample_json.keys():
                raise Exception("Invalid product")

            #> 80% of product titles are < 2 characters long
            if not sample_json["product_info"]["product_title"] or len(sample_json["product_info"]["product_title"]) < 2:
                count_product_titles_are_less_than_2_character_long = count_product_titles_are_less_than_2_character_long  + 1

            #> 80% of review counts are 0
            if not sample_json["reviews"]["review_count"] or sample_json["reviews"]["review_count"] == 0:
                count_review_counts_are_0 = count_review_counts_are_0  + 1

            #> 80% of product descriptions are < 2 words long
            if not sample_json["product_info"]["description"] or len(sample_json["product_info"]["description"]) < 2:
                count_product_descriptions_are_less_than_2_character_long = count_product_descriptions_are_less_than_2_character_long  + 1

            #> 80% of image counts are 0
            if not sample_json["page_attributes"]["image_count"] or sample_json["page_attributes"]["image_count"] == 0:
                count_image_counts_are_0 = count_image_counts_are_0  + 1

            #> 80% of products are out of stock
            if sample_json["sellers"]["owned_out_of_stock"] and sample_json["sellers"]["owned_out_of_stock"] == 1:
                count_products_are_out_of_stock = count_products_are_out_of_stock  + 1

            #UPC missing products
            if not sample_json["product_info"]["upc"]:
                upc_missing_product_list.append({"store url": sample_json["url"], "regression report url": "http://regression.contentanalyticsinc.com:8080/regression/console/urlsample/" + str(row["id"])})

            #Review issue products
            if sample_json["reviews"]["review_count"] > 0 and \
                    (sample_json["reviews"]["average_review"] is None or sample_json["reviews"]["max_review"] is None or sample_json["reviews"]["min_review"] is None or sample_json["reviews"]["reviews"] is None):
                review_issue_product_list.append({"store url": sample_json["url"], "regression report url": "http://regression.contentanalyticsinc.com:8080/regression/console/urlsample/" + str(row["id"])})

            #Price issue products
            if sample_json["sellers"]["price"] and (sample_json["sellers"]["price_amount"] is None or sample_json["sellers"]["price_currency"] is None):
                price_issue_product_list.append({"store url": sample_json["url"], "regression report url": "http://regression.contentanalyticsinc.com:8080/regression/console/urlsample/" + str(row["id"])})

            #Marketplace issue products
            if ((sample_json["marketplace_sellers"] and not sample_json["marketplace_prices"]) or (not sample_json["marketplace_sellers"] and sample_json["marketplace_prices"])) \
                    or ((sample_json["marketplace_sellers"] and sample_json["marketplace_prices"]) and len(sample_json["marketplace_sellers"]) != len(sample_json["marketplace_prices"])):
                marketplace_issue_product_list.append({"store url": sample_json["url"], "regression report url": "http://regression.contentanalyticsinc.com:8080/regression/console/urlsample/" + str(row["id"])})

            #Walmart v1 products
            if website == "walmart" and sample_json["scraper"] == "Walmart v1":
                walmart_v1_product_list.append({"store url": sample_json["url"], "regression report url": "http://regression.contentanalyticsinc.com:8080/regression/console/urlsample/" + str(row["id"])})
        except:
            invalid_products_list.append(row["url"])


    sql_changed_products = "select id, sample_url, website, changes_in_structure, sample_json, current_json from console_reportresult where report_date = '{0}' and website='{1}'".format(today.isoformat(), website)

    cur.execute(sql_changed_products)
    rows = cur.fetchall()
    rows = sorted(rows, key=lambda k: k['changes_in_structure'], reverse=True)

    #UPC missing issue
    csv_file_name_upc_missed = "/home/ubuntu/tmtext/special_crawler/jenkins/{0}_upc_missed_{1}.csv".format(website, time.strftime("%Y_%m_%d"))

    if upc_missing_product_list:
        field_names = ["store url", "regression report url"]
        csv_file = open(csv_file_name_upc_missed, "w")
        csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        csv_writer.writeheader()

        for product in upc_missing_product_list:
            for key in product.keys():
                product[key] = unicode(product[key]).encode("utf-8")

            csv_writer.writerow(product)

        csv_file.close()

        with open(csv_file_name_upc_missed, 'rb') as f_in, gzip.open(csv_file_name_upc_missed + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)


    #Review issue
    csv_file_name_review_issue = "/home/ubuntu/tmtext/special_crawler/jenkins/{0}_review_issue_{1}.csv".format(website, time.strftime("%Y_%m_%d"))

    if review_issue_product_list:
        field_names = ["store url", "regression report url"]
        csv_file = open(csv_file_name_review_issue, "w")
        csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        csv_writer.writeheader()

        for product in review_issue_product_list:
            for key in product.keys():
                product[key] = unicode(product[key]).encode("utf-8")

            csv_writer.writerow(product)

        csv_file.close()

        with open(csv_file_name_review_issue, 'rb') as f_in, gzip.open(csv_file_name_review_issue + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    #Price issue
    csv_file_name_price_issue = "/home/ubuntu/tmtext/special_crawler/jenkins/{0}_price_issue_{1}.csv".format(website, time.strftime("%Y_%m_%d"))

    if price_issue_product_list:
        field_names = ["store url", "regression report url"]
        csv_file = open(csv_file_name_price_issue, "w")
        csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        csv_writer.writeheader()

        for product in price_issue_product_list:
            for key in product.keys():
                product[key] = unicode(product[key]).encode("utf-8")

            csv_writer.writerow(product)

        csv_file.close()

        with open(csv_file_name_price_issue, 'rb') as f_in, gzip.open(csv_file_name_price_issue + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    #Marketplace issue
    csv_file_name_marketplace_issue = "/home/ubuntu/tmtext/special_crawler/jenkins/{0}_marketplace_issue_{1}.csv".format(website, time.strftime("%Y_%m_%d"))

    if marketplace_issue_product_list:
        field_names = ["store url", "regression report url"]
        csv_file = open(csv_file_name_marketplace_issue, "w")
        csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        csv_writer.writeheader()

        for product in marketplace_issue_product_list:
            for key in product.keys():
                product[key] = unicode(product[key]).encode("utf-8")

            csv_writer.writerow(product)

        csv_file.close()

        with open(csv_file_name_marketplace_issue, 'rb') as f_in, gzip.open(csv_file_name_marketplace_issue + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    #Walmart v1 products
    csv_file_name_walmart_v1 = "/home/ubuntu/tmtext/special_crawler/jenkins/{0}_walmart_v1_products_{1}.csv".format(website, time.strftime("%Y_%m_%d"))

    if walmart_v1_product_list:
        field_names = ["store url", "regression report url"]
        csv_file = open(csv_file_name_walmart_v1, "w")
        csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
        csv_writer.writeheader()

        for product in walmart_v1_product_list:
            for key in product.keys():
                product[key] = unicode(product[key]).encode("utf-8")

            csv_writer.writerow(product)

        csv_file.close()

        with open(csv_file_name_walmart_v1, 'rb') as f_in, gzip.open(csv_file_name_walmart_v1 + ".gz", 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

    field_names = ["store url", "number of changed parts", "version changed(Yes/No)", "regression report url"]
    csv_file_name_product_changes = "/home/ubuntu/tmtext/special_crawler/jenkins/{0}_product_changes_{1}.csv".format(website, time.strftime("%Y_%m_%d"))
    csv_file = open(csv_file_name_product_changes, "w")
    csv_writer = csv.DictWriter(csv_file, fieldnames=field_names)
    csv_writer.writeheader()

    number_of_changed_products = 0
    number_of_version_changed_products = 0

    for row in rows:
        sample_json = json.loads(row["sample_json"])
        current_json = json.loads(row["current_json"])

        if row["changes_in_structure"] > 0:
            number_of_changed_products = number_of_changed_products + 1
            version_changed = "No"

            try:
                if sample_json["scraper"] != current_json["scraper"]:
                    number_of_version_changed_products = number_of_version_changed_products + 1
                    version_changed = "Yes"

                csv_writer.writerow({"store url": unicode(row["sample_url"]).encode("utf-8"),
                                     "number of changed parts": unicode(str(row["changes_in_structure"])).encode("utf-8"),
                                     "version changed(Yes/No)": unicode(version_changed).encode("utf-8"),
                                     "regression report url": unicode("http://regression.contentanalyticsinc.com:8080/regression/console/reportresult/" + str(row["id"])).encode("utf-8")})
            except:
                continue

    csv_file.close()

    with open(csv_file_name_product_changes, 'rb') as f_in, gzip.open(csv_file_name_product_changes + ".gz", 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)

    percentage_of_changed_products = (float(number_of_changed_products) / float(number_of_reported_products)) * float(100)
    possibility_of_overall_website_changes = "No"

    if percentage_of_changed_products > 80:
        sites_changed += "%s\n" % website
        possibility_of_overall_website_changes = "Yes"

    possibility_of_80_percent_product_titles_are_less_than_2_character_long = "No"
    possibility_of_80_percent_review_counts_are_0 = "No"
    possibility_of_80_percent_product_descriptions_are_less_than_2_character_long = "No"
    possibility_of_80_percent_image_counts_are_0 = "No"
    possibility_of_80_percent_products_are_out_of_stock = "No"

    #> 80% of product titles are < 2 characters long
    if float(float(count_product_titles_are_less_than_2_character_long) / float(number_of_reported_products)) > 0.8:
        possibility_of_80_percent_product_titles_are_less_than_2_character_long = "Yes"
    #> 80% of review counts are 0
    if float(float(count_review_counts_are_0) / float(number_of_reported_products)) > 0.8:
        possibility_of_80_percent_review_counts_are_0 = "Yes"
    #> 80% of product descriptions are < 2 words long
    if float(float(count_product_descriptions_are_less_than_2_character_long) / float(number_of_reported_products)) > 0.8:
        possibility_of_80_percent_product_descriptions_are_less_than_2_character_long = "Yes"
    #> 80% of image counts are 0
    if float(float(count_image_counts_are_0) / float(number_of_reported_products)) > 0.8:
        possibility_of_80_percent_image_counts_are_0 = "Yes"
    #> 80% of products are out of stock
    if float(float(count_products_are_out_of_stock) / float(number_of_reported_products)) > 0.8:
        possibility_of_80_percent_products_are_out_of_stock = "Yes"

    website_header = "- " + website + "\n" + "Total tested product numbers: %d\n" \
                                             "Not a product count: %d\n" \
                                             "Product numbers of content structure changed: %d\n" \
                                             "Product numbers of version changed: %d\n" \
                                             "Percentage of changed products: %f\n" \
                                             "80 percent of product titles are < 2 characters long: %s\n" \
                                             "80 percent of review counts are 0: %s\n" \
                                             "80 percent of product descriptions are < 2 words long: %s\n" \
                                             "80 percent of image counts are 0: %s\n" \
                                             "80 percent of products are out of stock: %s\n" \
                                             "Possibility of overall website changes: %s\n\n" % (
                                                 number_of_reported_products,
                                                 number_of_not_a_product,
                                                 number_of_changed_products,
                                                 number_of_version_changed_products,
                                                 percentage_of_changed_products,
                                                 possibility_of_80_percent_product_titles_are_less_than_2_character_long,
                                                 possibility_of_80_percent_review_counts_are_0,
                                                 possibility_of_80_percent_product_descriptions_are_less_than_2_character_long,
                                                 possibility_of_80_percent_image_counts_are_0,
                                                 possibility_of_80_percent_products_are_out_of_stock,
                                                 possibility_of_overall_website_changes)
    email_content += (website_header)

    newdata = [number_of_reported_products, number_of_not_a_product, number_of_changed_products, number_of_version_changed_products, "%.2f" % percentage_of_changed_products, possibility_of_80_percent_product_titles_are_less_than_2_character_long, possibility_of_80_percent_review_counts_are_0, possibility_of_80_percent_product_descriptions_are_less_than_2_character_long, possibility_of_80_percent_image_counts_are_0, possibility_of_80_percent_products_are_out_of_stock, possibility_of_overall_website_changes]
    newdatahtml += "<td>"
    newdatahtml += "<br />"
    for d in newdata:
        newdatahtml += "<p>%s</p>" % d
    newdatahtml += "</td>"

    for i in range(0,len(keys)-1):
        sql = "UPDATE email_history SET {0} = \'{1}\' WHERE website = \'{2}\' AND day = 1".format(keys[i],newdata[i],website)
        cur.execute(sql)

    if os.path.isfile(csv_file_name_product_changes + ".gz"):
        csv_file = MIMEApplication(open(csv_file_name_product_changes + ".gz", "rb").read())
        csv_file.add_header('Content-Disposition', 'attachment', filename=basename(csv_file_name_product_changes + ".gz"))
        msg.attach(csv_file)

    if os.path.isfile(csv_file_name_upc_missed + ".gz"):
        csv_file1 = MIMEApplication(open(csv_file_name_upc_missed + ".gz", "rb").read())
        csv_file1.add_header('Content-Disposition', 'attachment', filename=basename(csv_file_name_upc_missed + ".gz"))
        msg.attach(csv_file1)

    if os.path.isfile(csv_file_name_review_issue + ".gz"):
        csv_file1 = MIMEApplication(open(csv_file_name_review_issue + ".gz", "rb").read())
        csv_file1.add_header('Content-Disposition', 'attachment', filename=basename(csv_file_name_review_issue + ".gz"))
        msg.attach(csv_file1)

    if os.path.isfile(csv_file_name_price_issue + ".gz"):
        csv_file1 = MIMEApplication(open(csv_file_name_price_issue + ".gz", "rb").read())
        csv_file1.add_header('Content-Disposition', 'attachment', filename=basename(csv_file_name_price_issue + ".gz"))
        msg.attach(csv_file1)

    if os.path.isfile(csv_file_name_marketplace_issue + ".gz"):
        csv_file1 = MIMEApplication(open(csv_file_name_marketplace_issue + ".gz", "rb").read())
        csv_file1.add_header('Content-Disposition', 'attachment', filename=basename(csv_file_name_marketplace_issue + ".gz"))
        msg.attach(csv_file1)

    if os.path.isfile(csv_file_name_walmart_v1 + ".gz"):
        csv_file1 = MIMEApplication(open(csv_file_name_walmart_v1 + ".gz", "rb").read())
        csv_file1.add_header('Content-Disposition', 'attachment', filename=basename(csv_file_name_walmart_v1 + ".gz"))
        msg.attach(csv_file1)

if sites_changed == "":
    sites_changed = "None"

html += "</tr>"
html += "<tr>"
html += "<td><b><p>{0}:</b></p>".format(date.today().isoformat()) + cathtml + "</td>"
html += newdatahtml
html += "</tr>"
html += "<tr>"
html += "<td><p><b>{0}:</b></p>".format((date.today() - timedelta(1)).isoformat()) + cathtml + "</td>"
for d in day1:
    html += "<td>"
    html += "<br />"
    for k in keys:
        html += "<p>%s</p>" % d[k]
    html += "</td>"
html += "</tr>"
html += "<tr>"
html += "<td><p><b>{0}:</b></p>".format((date.today() - timedelta(2)).isoformat()) + cathtml + "</td>"
for d in day2:
    html += "<td>"
    html += "<br />"
    for k in keys:
        html += "<p>%s</p>" % d[k]
    html += "</td>"
html += "</tr>"
html += "<tr>"
html += "<td><p><b>{0}:</b></p>".format((date.today() - timedelta(3)).isoformat()) + cathtml + "</td>"
for d in day3:
    html += "<td>"
    html += "<br />"
    for k in keys:
        html += "<p>%s</p>" % d[k]
    html += "</td>"
html += "</tr>"
html += "<tr>"
html += "<td><p><b>{0}:</b></p>".format((date.today() - timedelta(4)).isoformat()) + cathtml + "</td>"
for d in day4:
    html += "<td>"
    html += "<br />"
    for k in keys:
        html += "<p>%s</p>" % d[k]
    html += "</td>"
html += "</tr>"
html += "</table>"

msg.attach(MIMEText(header_content + sites_changed + "\n"))
msg.attach(MIMEText(html, 'html'))
connection = boto.connect_ses(aws_access_key_id=AMAZON_SES_KEY,
                              aws_secret_access_key=AMAZON_SES_SECRET)
result = connection.send_raw_email(
    msg.as_string(),
    fromaddr, toaddrs)

con.commit()

#Change according to your settings
#smtp_server = 'email-smtp.us-east-1.amazonaws.com'
#smtp_username = 'AKIAI2XV5DZO5VTJ6LXQ'
#smtp_password = 'AgWhl58LTqq36BpcFmKPs++24oz6DuS/J1k2GrAmp1T6'
#smtp_port = '587'
#smtp_do_tls = True

"""
server = smtplib.SMTP(
    host = smtp_server,
    port = smtp_port,
    timeout = 10
)

server.set_debuglevel(10)
server.starttls()
server.ehlo()
server.login(smtp_username, smtp_password)
server.sendmail(fromaddr, toaddrs, msg.as_string())

print server.quit()
"""

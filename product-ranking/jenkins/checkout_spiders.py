import json
import subprocess
import uuid
import smtplib
import email.utils
from email.mime.text import MIMEText

tests = {"jcpenney": ({"product_data": '[{"url": "http://www.jcpenney.com/jf-j-ferrar-solid-dress-shirt-slim-fit/prod.jump?ppId=pp5006241671", "color":"Castle Rock"}]', "quantity": '1'},)
                      #{"product_data": '[{"url": "http://www.jcpenney.com/jf-j-ferrar-solid-dress-shirt-slim-fit/prod.jump?ppId=pp5006241671", "FetchAllColors": true}]', "quantity": '1'},
                     # {"product_data": '[{"url": "http://www.jcpenney.com/new-world-map-framed-wall-art/prod.jump?ppId=pp5006242224"}]', "quantity":"1"},
                      #{"product_data": '[{"url": "http://www.jcpenney.com/copley-cove-set-of-2-dining-chairs/prod.jump?ppId=pp5003960476"}]', "quantity":"3"})
         }


site = "jcpenney"


def _analize_result(result):
    stat = {}
    stat['id'] = bool(result.get('id', None))
    stat['url'] = bool(result.get('url', None))
    stat['price'] = bool(result.get('price', None))
    stat['price_on_page'] = bool(result.get('price_on_page', None))
    stat['name'] = bool(result.get('name', None))
    stat['quantity'] = bool(result.get('quantity', None))
    stat['order_total'] = bool(result.get('order_total', None))
    stat['order_subtotal'] = bool(result.get('order_subtotal', None))
    return stat


def _init_stats():
    return {'id': 0,
            'not_id': 0,
            'url': 0,
            'not_url': 0,
            'price': 0,
            'not_price': 0,
            'price_on_page': 0,
            'not_price_on_page': 0,
            'name': 0,
            'not_name': 0,
            'quantity': 0,
            'not_quantity': 0,
            'order_total': 0,
            'not_order_total': 0,
            'order_subtotal': 0,
            'not_order_subtotal': 0}


def _process_stats(acum_stats, new_stats):
    for key in new_stats:
        key_to_increment = key if new_stats[key] else 'not_' + key
        acum_stats[key_to_increment] += 1
    return acum_stats


def _combine_stats(global_stats, test_stats):
    for key in test_stats:
        global_stats[key] += test_stats[key]
    return global_stats


def _generate_report(global_stats):
    keys = filter((lambda x: 'not_' not in x), global_stats.keys())
    report = ""
    for key in keys:
        not_key = 'not_' + key
        total_products = global_stats[not_key] + global_stats[key]
        percent_errors = global_stats[not_key] / float(total_products)
        if percent_errors > 0.2:
            report += "Field %s have %2.2f%% of fails\n" % (key, percent_errors)

    return report


def _send_email(report_results, site):
    # Create the message
    fromaddr = "jenkins@contentanalyticsinc.com"
    toaddrs = [("")]# must be a list
    msg = MIMEText(report_results)
    msg['To'] = email.utils.formataddr(toaddrs[0])
    msg['From'] = email.utils.formataddr(('Jenkins', fromaddr))
    msg['Subject'] = "%s Checkout Spider - Regressions Tests" % site

    smtp_server = 'email-smtp.us-east-1.amazonaws.com'
    smtp_username = 'AKIAI2XV5DZO5VTJ6LXQ'
    smtp_password = 'AgWhl58LTqq36BpcFmKPs++24oz6DuS/J1k2GrAmp1T6'
    smtp_port = '587'

    server = smtplib.SMTP(
        host=smtp_server,
        port=smtp_port,
        timeout=10
    )
    server.set_debuglevel(10)
    server.starttls()
    server.ehlo()
    server.login(smtp_username, smtp_password)
    server.sendmail(fromaddr, toaddrs, msg.as_string())
    print server.quit()


def _execute_test(site, product_data, quantity):
    # Run program
    output_path = "/tmp/%s" % uuid.uuid4()
    cmd_exec = "scrapy crawl %s_checkout_products -a product_data=\'%s\' -a quantity=\'%s\' -t json -o \'%s\'" % (
        site, test['product_data'], test['quantity'], output_path)
    subprocess.call((cmd_exec), shell=True)

    # Process results
    test_stats = _init_stats()
    with open(output_path, 'r') as file:
        results = json.loads(file.read())
        print results
        for result in results:
            print result
            stats = _analize_result(result)
            test_stats = _process_stats(test_stats, stats)

    return test_stats


if __name__ == '__main__':
    global_stats = _init_stats()
    for test in tests[site]:
        test_stats = _execute_test(
            site, test['product_data'], test['quantity'])
        global_stats = _combine_stats(global_stats, test_stats)

    report_results = _generate_report(global_stats)
    print report_results
    if report_results:
        _send_email(report_results, site)
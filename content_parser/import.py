import re
import xml
import sys
import pg_parser
import kimberlyclark_parser

from ftplib import FTP
from StringIO import StringIO
from api_lib import *

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def import_file(file_name, file_content):
    try:
        if config['parser'] == 'pg':
            print 'USING PG PARSER'
            customer = config['customer']

            print 'IMPORTING TO', config['push'], 'FOR CUSTOMER', customer
            api_key, token = get_api_key_and_token(file_name, customer, config['push'])

            pg_parser.setup_parse(file_content, config['push'], api_key, token, customer)

        elif config['parser'] == 'kimberlyclark':
            print 'USING KIMBERLYCLARK PARSER'

            for customer in ('Master Data', 'Walmart.com', 'Amazon.com'):
                print 'IMPORTING TO', config['push'], 'FOR CUSTOMER', customer
                api_key, token = get_api_key_and_token(file_name, customer, config['push'])

                kimberlyclark_parser.setup_parse(file_content, config['push'], api_key, token, customer)

    except (ValueError, xml.etree.ElementTree.ParseError) as e:
        print 'Error parsing %s with %s template parser: %s' % (file_name, config['parser'], e.message)
        report_status(api_key, token, 4, config['push'])

    except Exception as e:
        print 'Exception', e
        report_status(api_key, token, 4, config['push'])


imported_file = False

if len(sys.argv) > 1:
    if sys.argv[1].endswith('.json'):
        with open(sys.argv[1], 'r') as c:
            config = json.loads(c.read())
        filenames = sys.argv[2:]
    else:
        with open('config.json', 'r') as c:
            config = json.loads(c.read())
        filenames = sys.argv[1:]

    for filename in sorted(filenames):
        imported_file = True

        with open(filename, 'r') as f:
            import_file(filename, f.read())
else:
    with open('config.json', 'r') as c:
        config = json.loads(c.read())


# Clear upcs files
if config['parser'] == 'pg':
    with open('all_pg_upcs.csv', 'w') as f:
        pass
    with open('missing_pg_upcs.csv', 'w') as f:
        pass
if config['parser'] == 'kimberlyclark':
    with open('all_kimberlyclark_upcs.csv', 'w') as f:
        pass
    with open('missing_kimberlyclark_upcs.csv', 'w') as f:
        pass


if not imported_file and config['import'] == 'FTP':
    print 'IMPORTING FROM FTP USING:', config['user'], config['passwd']

    ftp = FTP(config['ip']) 
    ftp.login(config['user'], config['passwd'])
    if config['path']:
        ftp.cwd(config['path'])

    file_names = ftp.nlst()
    file_names = filter(lambda _file: _file.endswith('.xml'), file_names)

    if config['from_date']:
        from_date = config['from_date'].split('_')
        YEAR, MONTH, DAY = (int(x) for x in from_date)

        if config['to_date']:
            to_date = config['to_date'].split('_')
            YEAR2, MONTH2, DAY2 = (int(x) for x in to_date)

        def filter_by_date(_file_name):
            m = re.match('kwikee_export(\d+)_(\d+)_(\d+)', _file_name)
            if m:
                year, month, day = (int(x) for x in m.groups())
                if year > YEAR or (year == YEAR and (month > MONTH or (month == MONTH and day >= DAY))):
                    if config['to_date']:
                        if year < YEAR or (year == YEAR and (month < MONTH or (month == MONTH and day <= DAY))):
                            return True
                    else:
                        return True

        file_names = filter(lambda _file: filter_by_date(_file), file_names)

    for filename in file_names:
        print 'FILE', filename
        r = StringIO()
        try:
            with open(filename, 'r') as f:
                file_str = f.read()
        except:
            print 'DIDN\'T FIND LOCALLY, FETCHING FROM FTP'

            for i in range(3):
                try:
                    ftp = FTP(config['ip']) 
                    ftp.login(config['user'], config['passwd'])
                    if config['path']:
                        ftp.cwd(config['path'])
                    ftp.retrbinary('RETR ' + filename, r.write)
                    break
                except:
                    print traceback.format_exc()

                    time.sleep(10)

            file_str = r.getvalue()

            with open(filename, 'w') as f:
                f.write(file_str)

        import_file(filename, file_str)

    msg = MIMEMultipart()

    to = ['mklein031993@gmail.com']

    name = 'KCC' if config['parser'] == 'kimberlyclark' else 'PG'

    msg['Subject'] = 'Missing UPCs in {} Master Data tab'.format(name)

    if config['parser'] == 'pg':
        to.append('import+cars@contentanalyticsinc.com')
        with open('missing_pg_upcs.csv', 'r') as f:
            msg.attach(MIMEText(f.read(), 'text'))

    if config['parser'] == 'kimberlyclark':
        to.append('import+kcc@contentanalyticsinc.com')
        with open('missing_kimberlyclark_upcs.csv', 'r') as f:
            msg.attach(MIMEText(f.read(), 'text'))

    s = smtplib.SMTP('localhost')
    s.sendmail('auto', to, msg.as_string())
    s.quit()

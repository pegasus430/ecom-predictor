__author__ = 'root'

#!/usr/bin/env python

import os
import re
import sys
import csv
import zlib
import traceback
from datetime import datetime

from subprocess import call
from subprocess import Popen

import smtplib
from email.mime.text import MIMEText


DEPARTMENTS_PATH = "/ebs-sftp/walmart/walmart/departments/"
DEPARTMENTS_OUTPUT_PATH = "/ebs-sftp/walmart/walmart/departments_output/"
GZ_FILE_PATH = DEPARTMENTS_PATH + 'ci_walmart_inbound_en_us.xml.gz'
XML_FILE_PATH = DEPARTMENTS_PATH + 'ci_walmart_inbound_en_us.xml'


def send_email(msg_txt, subject='ALERT', to='mklein031993@gmail.com'):
    msg = MIMEText(msg_txt)

    msg['Subject'] = subject
    msg['From'] = 'wm-departments server'
    msg['To'] = to

    s = smtplib.SMTP('localhost')
    s.sendmail('wm-departments', to, msg.as_string())
    s.quit()


def generate_department_product_list(output_dir):
    print 'GENERATING', output_dir

    with open(XML_FILE_PATH) as f:
        for line in f:
            try:
                if '<item>' in line:
                    url = None
                    super_department = 'unnav'
                    department = None
                    category = None
                    vendor_id = None
                    vendor_name = None

                elif '</item>' in line:
                    # don't write nonsense
                    if not url or not url.startswith('http'):
                        continue

                    marketplace_or_owned = 'owned' if not vendor_name or 'Walmart' in vendor_name else 'marketplace'

                    csv_file_name = '{}_{}.csv'.format(super_department, marketplace_or_owned).lower()

                    if os.path.isfile(output_dir + csv_file_name):
                        csv_file = open(output_dir + csv_file_name, 'a+')
                        csv_writer = csv.writer(csv_file)
                    else:
                        csv_file = open(output_dir + csv_file_name, 'w')
                        csv_writer = csv.writer(csv_file)

                        # write the headers
                        csv_writer.writerow(['url',
                                'super_department',
                                'department',
                                'category',
                                'vendor_id',
                                'vendor_name'])

                    csv_writer.writerow([url,
                            super_department,
                            department,
                            category,
                            vendor_id,
                            vendor_name])

                    csv_file.close()

                else:
                    # url and vendor_id
                    pu = re.search('<Product_URL>(.+?)</Product_URL>', line)
                    if pu:
                        url = pu.group(1).split('?')[0]
                        vendor_id = re.search('selectedSellerId=(\d+)', pu.group(1))
                        if vendor_id:
                            vendor_id = vendor_id.group(1)

                    # vendor_name
                    mpn = re.search('<Marketplace_Partner_Name>(.+?)</Marketplace_Partner_Name>', line)
                    if mpn:
                        vendor_name = mpn.group(1)

                    # super_department
                    dnt = re.search('<DEPT_NM_TRANSLATED>(.+?)</DEPT_NM_TRANSLATED>', line)
                    if dnt:
                        super_department = dnt.group(1)

                    # department and category
                    cpcpd = re.search('<CHAR_PRIM_CAT_PATH_DOT>(.+?)</CHAR_PRIM_CAT_PATH_DOT>', line)
                    if cpcpd:
                        cpcpd = cpcpd.group(1).split('.')
                        # first two are 'home page' and super_departnemnt
                        if len(cpcpd) > 2:
                            department = cpcpd[2]
                        if len(cpcpd) > 3:
                            category = cpcpd[3]

            except:
                print traceback.format_exc()

    '''
    # make output files uniq
    for filename in os.listdir(output_dir):
        if filename.endswith('.csv'):
            print 'UNIQ', filename

            filepath = output_dir + filename.replace(' ', '\ ').replace('&', '\&').replace(';', '\;')
            filepath_uniq = filepath + '.uniq'

            Popen('sort -u {0} > {1}'.format(filepath, filepath_uniq), shell=True).wait()
            Popen('mv {0} {1}'.format(filepath_uniq, filepath), shell=True)
    '''

    send_email('Generated ' + date_str)


def extract_xml():
    print 'EXTRACTING XML'

    CHUNKSIZE = 1024

    d = zlib.decompressobj(16 + zlib.MAX_WBITS)

    gz = open(GZ_FILE_PATH, 'rb')
    buffer = gz.read(CHUNKSIZE)

    xml = open(XML_FILE_PATH, 'wb')

    while buffer:
        outstr = d.decompress(buffer)
        xml.write(outstr)
        buffer = gz.read(CHUNKSIZE)

    outstr = d.flush()
    xml.write(outstr)

    gz.close()
    xml.close()


try:
    # TODO: for now, just exit
    #sys.exit(0)

    date_str = datetime.utcnow().strftime('%Y_%m_%d')

    output_path = DEPARTMENTS_OUTPUT_PATH + date_str + '/'

    # Create output directory for most recent date, exit if it already exists
    if os.path.exists(output_path):
        print 'Path %s exists, exiting' % output_path
        sys.exit(0)
    else:
        os.makedirs(output_path)

    # Extract xml file
    extract_xml()

    # Extract department files
    generate_department_product_list(output_path)

    # Generate count summary
    call(['python', DEPARTMENTS_OUTPUT_PATH + 'count.py', output_path])

except Exception as e:
    print e
    send_email(str(e))

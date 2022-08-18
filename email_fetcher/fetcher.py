import argparse
import logging
import os
import json
import imaplib
import email
import ftplib
import re
from email.utils import parsedate
from StringIO import StringIO
from zipfile import ZipFile
from datetime import datetime


logger = logging.getLogger(__name__)


def get_args():
    """
    Parse command line arguments

    :return: command line arguments
    """

    parser = argparse.ArgumentParser(description='Email fetcher.'
                                                 ' Fetch the latest email by subject and upload attachments to FTP')

    parser.add_argument('-c', '--config',
                        default='config.json',
                        help='Configuration JSON file')

    parser.add_argument('-l', '--log',
                        default='fetcher.log',
                        help='Log file')

    return parser.parse_args()


def setup_logger(log_level=logging.DEBUG, path=None):
    """
    Setup logger formats and handlers

    :param log_level: logging level
    :param path: log file path
    :return:
    """

    logger.setLevel(log_level)

    log_format = logging.Formatter('%(asctime)s %(levelname)s:%(message)s')
    log_format.datefmt = '%Y-%m-%d %H:%M:%S'

    log_stdout = logging.StreamHandler()
    log_stdout.setFormatter(log_format)
    log_stdout.setLevel(log_level)
    logger.addHandler(log_stdout)

    if path:
        log_file = logging.FileHandler(path)
        log_file.setFormatter(log_format)
        log_file.setLevel(log_level)
        logger.addHandler(log_file)


class EmailFetcher(object):

    def __init__(self, server):
        self.server = imaplib.IMAP4_SSL(server)

    def auth(self, box, password):
        self.server.login(box, password)
        self.server.select('Inbox')

    def get_attachments(self, subject, filename_format):
        _, data = self.server.search(None, '(UNSEEN)', '(Subject "{}")'.format(subject))
        mail_ids = data[0].split()

        logger.info('Found {} new emails'.format(len(mail_ids)))

        attachments = []

        if len(mail_ids) > 0:
            logger.info('Extracting attachments from emails')

            for mail_id in mail_ids:
                _, mail_content = self.server.fetch(mail_id, '(RFC822)')

                mail_body = mail_content[0][1]

                mail = email.message_from_string(mail_body)

                date = parsedate(mail.get('Date'))
                if date:
                    date = '-'.join(map(lambda x: '{:02}'.format(x), date[:3]))
                else:
                    date = datetime.now().strftime('%Y-%m-%d')

                for part in mail.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue

                    if part.get('Content-Disposition') is None:
                        continue

                    filename = part.get_filename()
                    name, ext = os.path.splitext(filename)

                    if ext in ('.zip', '.csv', '.xlsx', '.xls'):
                        logger.info('Found attachment: {}'.format(filename))
                        attachment_content = part.get_payload(decode=True)

                        if ext == '.zip':
                            zip = ZipFile(StringIO(attachment_content))

                            for src_filename in zip.namelist():
                                dst_filename = os.path.splitext(src_filename)
                                dst_filename = filename_format.format(subject=re.sub(r'\W+', '_', subject),
                                                                      name=dst_filename[0],
                                                                      date=date,
                                                                      ext=dst_filename[1])

                                attachments.append({
                                    'filename': dst_filename,
                                    'file': zip.open(src_filename)
                                })
                        else:
                            dst_filename = filename_format.format(subject=re.sub(r'\W+', '_', subject),
                                                                  name=name,
                                                                  date=date,
                                                                  ext=ext)

                            attachments.append({
                                'filename': dst_filename,
                                'file': StringIO(attachment_content)
                            })

        return attachments

    def close(self):
        self.server.close()
        self.server.logout()


class FtpUploader(object):

    def __init__(self, server):
        self.server = ftplib.FTP(server)

    def auth(self, user, password):
        self.server.login(user, password)

    def upload(self, dir_path, attachments):
        for attachment in attachments:
            logger.info('Uploading {}'.format(attachment['filename']))
            self.server.storbinary('STOR {}'.format(os.path.join(dir_path, attachment['filename'])),
                                   attachment['file'])


if __name__ == '__main__':

    args = get_args()

    setup_logger(path=args.log)
    logger.info('****')

    if not os.path.isfile(args.config):
        logger.error("Config file '{}' doesn't exist".format(args.config))

    try:
        config = json.load(open(args.config))
    except Exception as e:
        logger.error("Can't parse config file: {}".format(e))
        exit()

    for fetcher_config in config:
        logger.info('Starting {} fetcher'.format(fetcher_config.get('name')))

        try:
            ftp_config = fetcher_config.get('ftp', {})

            logger.info('Connecting to FTP server {}'.format(ftp_config.get('server')))
            ftp = FtpUploader(ftp_config.get('server'))

            logger.info('Authentication for user {}'.format(ftp_config.get('user')))
            ftp.auth(ftp_config.get('user'), ftp_config.get('password'))

            email_config = fetcher_config.get('email', {})

            logger.info('Connecting to EMAIL server {}'.format(email_config.get('server')))
            fetcher = EmailFetcher(email_config.get('server'))

            logger.info('Authentication for box {}'.format(email_config.get('box')))
            fetcher.auth(email_config.get('box'), email_config.get('password'))

            for subject, filename_format in email_config.get('subjects', {}).iteritems():
                logger.info('Searching for subject: {}'.format(subject))
                attachments = fetcher.get_attachments(subject, filename_format)

                if attachments:
                    logger.info('Uploading files')
                    ftp.upload(ftp_config.get('dir'), attachments)

            logger.info('Closing connection')
            fetcher.close()
        except Exception as e:
            logger.error('{}'.format(e))

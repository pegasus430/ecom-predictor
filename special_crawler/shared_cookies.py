import boto
import pickle
import requests
import traceback
from boto.s3.key import Key

class SharedCookies:

    def __init__(self, scraper_name):
        self.amazon_bucket_name = 'ch-settings'
        self.shared_cookies_filename = '{}.cookies'.format(scraper_name)
        try:
            S3_CONN = boto.connect_s3(is_secure=False)
            S3_BUCKET = S3_CONN.get_bucket(self.amazon_bucket_name, validate=False)
            self.k = Key(S3_BUCKET)
            self.k.key = self.shared_cookies_filename
            if not self.k.exists():
                self.k.set_contents_from_string('')
        except:
            print(traceback.format_exc())

    def save(self, session):
        if hasattr(self, 'k'):
            try:
                self.k.set_contents_from_string(
                    pickle.dumps(requests.utils.dict_from_cookiejar(session.cookies))
                )
            except:
                print(traceback.format_exc())

    def load(self):
        if hasattr(self, 'k'):
            try:
                return requests.utils.cookiejar_from_dict(
                    pickle.loads(self.k.get_contents_as_string())
                )
            except:
                print(traceback.format_exc())

    def delete(self):
        if hasattr(self, 'k'):
            try:
                self.k.set_contents_from_string('')
            except:
                print(traceback.format_exc())

class SharedLock:

    def __init__(self, scraper_name):
        self.amazon_bucket_name = 'ch-settings'
        self.shared_lock_filename = '{}.lock'.format(scraper_name)
        try:
            S3_CONN = boto.connect_s3(is_secure=False)
            S3_BUCKET = S3_CONN.get_bucket(self.amazon_bucket_name, validate=False)
            self.k = Key(S3_BUCKET)
            self.k.key = self.shared_lock_filename
            if not self.k.exists():
                self.k.set_contents_from_string('')
        except:
            print(traceback.format_exc())

    def save(self, value):
        if hasattr(self, 'k'):
            try:
                self.k.set_contents_from_string(value)
            except:
                print(traceback.format_exc())

    def load(self):
        if hasattr(self, 'k'):
            try:
                return bool(self.k.get_contents_as_string())
            except:
                print(traceback.format_exc())

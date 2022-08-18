import sqlite3

class StoreLogs(object):
    """docstring for StoreLogs"""
    def __init__(self):
        self.conn = sqlite3.connect('tests_logs.db')

        self.c = self.conn.cursor()

        # Create table
        self.c.execute('''DROP TABLE IF EXISTS reviews''')
        self.c.execute('''CREATE TABLE reviews
                     (url text, error_message text, reviews_source text, reviews_js text, \
                         average_source real, average_js real, nr_reviews_source integer, nr_revirews_js integer)''')

    # store info from reviews test below (test_reviews_correct)
    # in a way that makes it easier to investigate the data
    # args:
    #     url - url of product in question
    #   error_message - what assertion was false, its error message
    #   reviews_source - reviews object extracted from source
    #   reviews_js - reviews object extracted from javascript
    #   average_source - average reviews value for reviews extracted from source
    #   average_js - average reviews value for reviews extracted from javascript
    #   nr_reviews_source - nr reviews value for reviews extracted from source
    #   nr_reviews_js - nr reviews value for reviews extracted from javascript
    def store_reviews_logs(self, url, error_message, reviews_source, reviews_js, \
        average_source=None, average_js=None, nr_reviews_source=None, nr_reviews_js=None):

        self.c.execute("INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?)", \
            (url, error_message, reviews_source, reviews_js, average_source, average_js, nr_reviews_source, nr_reviews_js))

        self.conn.commit()

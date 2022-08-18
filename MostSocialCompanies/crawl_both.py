from optparse import OptionParser
from datetime import datetime, timedelta

import re
import csv

class Utils:

    # return a list of dates for all days in a date range
    @staticmethod
    def daterange(start_date, end_date):
        for n in range(int ((end_date - start_date).days)):
            yield start_date + timedelta(n)

    # read site youtube usernames from csv input file
    @staticmethod
    def input_sites(filename):
        csvfile = open(filename, "rw")

        sites = []

        sitesreader = csv.reader(csvfile, delimiter=',')

        # exclude header
        sitesreader.next()

        for row in sitesreader:
            site = {}

            #TODO: maybe work with name indexes (insted of number)
            site["site"] = row[1]
            site["twitter_username"] = row[2]
            # remove "@" prefix from twitter username
            m = re.match("@(.*)", site['twitter_username'])
            if m:
                site['twitter_username'] = m.group(1)
            site["yt_username"] = row[3]
            sites.append(site)

        csvfile.close()

        #print 'read all'

        return sites

    # output results to csv file
    @staticmethod
    def output_all(filename, results):
        csvfile = open(filename, "wb+")

        siteswriter = csv.writer(csvfile, delimiter=',')
        siteswriter.writerow(["Date", "Brand", "Followers", "Following", "Tweets", \
            "All_Tweets", "YT_Video", "YT_All_Videos", "YT_Views", "YT_All_Views"])

        for (date, item) in results:
            siteswriter.writerow([date, item['brand'], '', '', '', '', item['video_titles'], item['all_videos_count'], item['all_views_count']])
        print results

        csvfile.close()
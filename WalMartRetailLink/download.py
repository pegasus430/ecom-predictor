import argparse
import os
import sys

from spider import retail_link


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('Error: %s\n' % message)
        self.print_help(sys.stderr)
        self.exit(2)


class WalmartRetailCrawler(retail_link.WalmartRetailCrawler):
    resources_dir = '.'
    bucket_name = None


parser = ArgumentParser(description='Download the report.')
parser.add_argument('user', help='Login user.')
parser.add_argument('password', help='Login password.')
parser.add_argument('report_name', help='Name of the report.')

args = parser.parse_args()

try:
    sys.stdout = open(os.devnull, 'w')
    crawler = WalmartRetailCrawler()
    crawler.do_login(args.user, args.password)
    report = crawler.get_report(args.report_name)
    sys.stdout = sys.__stdout__
except retail_link.WalmartRetailCrawlerException as e:
    sys.stdout = sys.__stdout__
    print 'Error: %s' % e.message
else:
    print 'The report was downloaded to: %s' % os.path.abspath(report)

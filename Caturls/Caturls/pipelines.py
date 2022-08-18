# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/topics/item-pipeline.html
import json

class CaturlsPipeline(object):
    def __init__(self):
        self.urls = []

    def open_spider(self, spider):
        self.file = open(spider.outfile, 'wb')

        # if categories should be parsed too, make this a csv
        # add header row
        if spider.with_categories:
            self.file.write("ProductURL,Cat\n")    
    
    def process_item(self, item, spider):
        line = item['product_url']
        ## avoid duplicates
        #if item['product_url'] not in self.urls:
        self.urls.append(item['product_url'])

        # if the spider classifies by category, add category info the the output
        if spider.with_categories:
            assert 'category' in item
            line += "," + json.dumps(item['category']) # enquote category name

        # write to file
        line += "\n"
        self.file.write(line)

        return item

    def close_spider(self, spider):
        self.file.close()

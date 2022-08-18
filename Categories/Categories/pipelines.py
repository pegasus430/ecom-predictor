# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/topics/item-pipeline.html

import json

# write each JSON object on one line
class LinesPipeline(object):
    def open_spider(self, spider):
        if hasattr(spider, 'outfile') and spider.outfile:
            filename = outfile
        else:
            filename = spider.name + "_categories.jl"
        self.file = open(filename, 'wb')

    def process_item(self, item, spider):
        line = json.dumps(dict(item)) + "\n"
        self.file.write(line)
        return item

# write each JSON object on one line, lines separated by commas
class CommaSeparatedLinesPipeline(object):

    # categories tree - tree of entire sitemap structured as dictionary with keys being category ids (catid field)
    # and values being dictionaries containing:
    # - item represented by that URL
    # - list of subcategories of that item (just their URLs)
    # if compute_nrproducts flag is on in spider, this tree will be built and used to aggregate number of products for each category where it's not explicitly specified on the site
    categories_tree = {}

    # store list of ids of all top level categories (departments). needed for categories tree traversal
    top_level_categories = []

    def __init__(self):
        # flag indicating if the first item has been written to output
        self.started = False


    def open_spider(self, spider):
        if hasattr(spider, 'outfile') and spider.outfile:
            filename = spider.outfile
        else:
            filename = spider.name + "_categories.jl"
        self.file = open(filename, 'wb')

    # process item in spider for which we build the sitemap tree
    def process_item_fortree(self, item, spider):
        # add key-value pair where key is current's item category id
        # and value is dict containing item and subcategories list (for now empty)
        self.categories_tree[item['catid']] = {}
        self.categories_tree[item['catid']]['item'] = item

        # create subcategories list if it doesn't exist (may have been created by previous items)
        if 'subcategories' not in self.categories_tree[item['catid']]:
            self.categories_tree[item['catid']]['subcategories'] = []

        # add to top level categories if it's a department
        if item['level'] == spider.DEPARTMENT_LEVEL:
            self.top_level_categories.append(item['catid'])
        
        # add item key (catid) to subcategories list of its parent's element in the tree
        # create parent item in categories tree if it doesn't exist
        if 'parent_catid' in item:
            if item['parent_catid'] not in self.categories_tree:
                self.categories_tree[item['parent_catid']] = {'subcategories': []}
            # append url to the parent's subcategories list
            # if 'subcategories' not in self.categories_tree[item['parent_catid']]:
            #     self.categories_tree[item['parent_catid']] = []
            self.categories_tree[item['parent_catid']]['subcategories'].append(item['catid'])

    def process_item(self, item, spider):
        if hasattr(spider, 'compute_nrproducts') and spider.compute_nrproducts:
            self.process_item_fortree(item, spider)
        else:
            # if we're not aggregating number of products, just return the item
            line = json.dumps(dict(item))
            if self.started:
                self.file.write(",\n" + line)
            else:
                self.file.write(line)
                self.started = True
            return item


    # complete nr_products field for all categories in the tree where it is missing
    def compute_item_counts(self):
        # do a depth first count for all top level categories
        for key in self.top_level_categories:
            category_item = self.categories_tree[key]['item']
            if 'nr_products' not in category_item:

                # compute nr_products from dict output of depth_first_count
                count_dict = self.depth_first_count(key)
                category_item['nr_products'] = sum(count_dict.values())

    # complete nr_products field for all categories in the tree where it is missing, by using its children categories
    # use depth-first traversal to collect all nr_products info for each category's subcategory
    # return dictionary containing all product counts to be added to compute current one, indexed by item[key_field]
    def depth_first_count(self, key, key_field='url'):
        # build dictionary with keys (by default = URLs) of subcategories whose item count to add to current one, values = their item count
        # this avoids duplicate subcategories and inaccurate final item counts (they are duplicates in terms of their pages' URLs)
        # use dicionary to compute product count and add product count to current item; then return dictionary

        # if it's available as extracted from the site, use that
        if 'nr_products' in self.categories_tree[key]['item']:
            count_dict = {self.categories_tree[key]['item'][key_field] : self.categories_tree[key]['item']['nr_products']}
            # no need to set its item's product count, it is already set

            return count_dict

        # else - if it's not available as extracted from the site, compute it from its subcategories

        if 'subcategories' in self.categories_tree[key]:
            subcategories = self.categories_tree[key]['subcategories']

            count_dict = {}

        # collect item count from all subcategories

            #TODO: problem: sometimes the same subcategory (URL) appears under different category subtrees, even different levels. it will end up being counted twice...
            # example: Wine Racks, see its parents, both of the same department
            for subcategory in subcategories:
                if 'nr_products' in self.categories_tree[subcategory]['item']:
                    subcategory_count_dict = {self.categories_tree[subcategory]['item'][key_field] : self.categories_tree[subcategory]['item']['nr_products']}

                else:
                    subcategory_count_dict = self.depth_first_count(subcategory)

                # add subcategory categories dict to its parent's dict
                count_dict.update(subcategory_count_dict)

            # compute current item's product count based on its subcategories dict
            nr_products = sum(count_dict.values())

            # add its item count to its
            self.categories_tree[key]['item']['nr_products'] = nr_products

            #print count_dict

            return count_dict

        # if there are no subcategories and no product count, return 0
        if 'subcategories' not in self.cateogries_tree[key] or not self.categores_tree[key]['subcategories']:
            if 'nr_products' in self.categories_tree[key]:
                nr_products = self.categories_tree[key]['nr_products']
            else:
                nr_products = 0

            count_dict = {self.categories_tree[key]['item'][key_field] : nr_products}
            return count_dict


    def close_spider(self, spider):
        # if spider uses category tree, then all the output needs to be written to file now
        if hasattr(spider, 'compute_nrproducts') and spider.compute_nrproducts:
            # compute all nr_products for all categories using the tree
            self.compute_item_counts()
            for key in self.categories_tree:

                #TEST: to use with test_categories: if set, some categories won't have 'item' (I guess?)
                if not 'item' in self.categories_tree[key] and hasattr(spider, 'test_category') and spider.test_category:
                    continue

                # if 'item' not in self.categories_tree[key]:
                #     print "NO ITEM FOR", key
                line = json.dumps(dict(self.categories_tree[key]['item']))
                if self.started:
                    self.file.write(",\n" + line)
                else:
                    self.file.write(line)
                    self.started = True
        else:
            # otherwise just close the file (items were output in process_item)
            self.file.close()


# write entire content as a JSON object in the output file
class JSONObjectPipeline(object):
    def __init__(self):
        self.items = []

    def open_spider(self, spider):
        filename = spider.name + "_categories.jl"
        self.file = open(filename, 'wb')

    def process_item(self, item, spider):
        self.items.append(item)
        return item

    def close_spider(self, spider):
        l = [dict(x) for x in self.items]
        o = {"data" : l}
        self.file.write(json.dumps(o))

        self.file.close()


import pygraphviz as pgv
import networkx as nx
import re

class TargetCategories():

    def __init__(self, infile="categories-target-urls-firstlev.txt"):
        self.categories = set()
        self.categories_urls = {}
        # this file contains only categories not split by /
        with open(infile) as catfile:
            for l in catfile:
                # extract just category name
                cat = re.match("/c/([^/]+)/.*", l.strip()).group(1)
                self.categories.add(cat)
                # add category's url to dictionary
                # try to add the url with least / (no subcategories delimited by / if possible) - purest form
                # and from among these, the one that is shortest: part after /-/N... can have some extra letters that change the page content a bit?
                potential_url = "http://www.target.com" + l.strip()
                if (cat not in self.categories_urls) or (potential_url.count('/') < self.categories_urls[cat].count('/')) \
                or (len(potential_url) < len(self.categories_urls[cat])):
                    self.categories_urls[cat] = potential_url

        self.categories_items = []

        for category in self.categories:
            item = {}
            item['name'] = category
            item['url'] = self.categories_urls[category]
            parent = ""
            for potential_parent in self.categories:
                # find longest category that is prefix or suffix to current category
                if (category.startswith(potential_parent) or category.endswith(potential_parent)) \
                and potential_parent!=category and len(potential_parent) > len(parent):
                    parent = potential_parent
            item['parent'] = parent

            self.categories_items.append(item)

    # print to stdout urls of categories without parents
    def print_orphans(self):
        # categories without parents
        categories_without_parents = filter(lambda x: x['parent'] == '', self.categories_items)
        # print their urls
        for cwp in categories_without_parents:
            print self.categories_urls[cwp['name']]

    #TODO: find a way to compute levels and include them in categories_items

    # return list of categories items containing their names, urls and parents
    def get_categories_tree(self):
        return self.categories_items

    def draw_categories_graphs(self):
        # filter only categories with parents
        categories_with_parents = filter(lambda x: x['parent'] != '', self.categories_items)

        # build categories graph
        G = nx.Graph()
        for category in categories_with_parents:
            G.add_edge(category['name'], category['parent'])

        # extract connected components
        connected_components = nx.connected_component_subgraphs(G)

        #print len(connected_components)

        graph_nr=0

        # create graphs directory if it doesn't exist
        if not os.path.exists("graphs"):
            os.makedirs("graphs")

        # draw each connected component to a graphviz file
        for concomp in connected_components:
            filename = "graphs/graph" + str(graph_nr) + ".png"
            graph_nr += 1
            D = pgv.AGraph()
            D.edge_attr.update(color="blue", len="5.0", width="2.0")
            for (child, parent) in concomp.edges():
                D.add_edge(child, parent)
            D.layout()
            D.draw(filename)

if __name__=="__main__":
    t = TargetCategories()
    t.print_orphans()
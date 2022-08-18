#!/usr/bin/python

import codecs
import json
import itertools
import re
from pprint import pprint
import nltk
from nltk.corpus import stopwords
import networkx as nx

class Utils:

    # static variable that holds a dictionary of stems and their full words
    # is built in normalize() function, using words from its parameters
    stems = {}

    # static variable that holds a dictionary of lowercased words and their original corresponding words
    # is built in normalize() function, using words from its parameters
    upper = {}

    # normalizes a text: tokenizing, lowercasing, eliminating stopwords, stemming
    # (add synonyms?)
    # returns list of tokens
    @classmethod
    def normalize(cls, text):
        # eliminate non-word characters
        text = re.sub("[^\w\s]","",text)

        # replace unicode character in "Decor"
        pattern = re.compile(u'\uFFFD', re.UNICODE)
        text = re.sub(pattern, "e", text)

        # Exceptions - handling some phrases separately
        #TODO: do this more ellegantly
        # Exclude "Home Theater", put it together with electronics
        text = text.replace("Home Theater", "Electronics")
        # Exclude "Cloud Player for Home"
        text = text.replace("Cloud Player for Home","Cloud Player")
        text = text.replace("Home & Portable Audio", "Portable Audio")
        #print text

        stopset = set(stopwords.words('english'))#["and", "the", "&", "for", "of", "on", "as", "to", "in"]
        stemmer = nltk.PorterStemmer()
        tokens = nltk.WordPunctTokenizer().tokenize(text)
        clean = [token.lower() for token in tokens if token.lower() not in stopset and len(token) > 0]
        final = [stemmer.stem(word) for word in clean]

        # Fill tokens and stems dictionaries
        for token in tokens:
            cls.upper[token.lower()] = token

        for index in range(len(final)):
            if final[index] not in cls.stems:
                cls.stems[final[index]] = cls.upper[clean[index]]

        return final

    # merge 2 lists of dictionaries without duplicates
    # where a duplicate is an item with the same value for every key in keys
    # assuming dictionary values are lists, and they both have all the keys in key
    @staticmethod
    def merge_dictionaries(list1, list2, keys):
        final_list = []

        for element1 in list1 + list2:
            # if element in conjoined lists is different from all the elements in final list (it hasn't been added yet)
            # if final list is empty add the element
            if not final_list:
                final_list.append(element1)
            # the element is not found in final list
            notfound = True
            for element2 in final_list:
                # if they are different in values for every key in keys list
                different = False
                for key in keys:
                    if element1[key]!=element2[key]:
                        different = True
                        break
                if not different:
                    notfound = False
                    break
            if (notfound):
                final_list.append(element1)
        return final_list

class Categories:

    def __init__(self, sites, level=1):
        self.sites = sites
        self.level = level

        # words not to group by (their normalized version)
        self.exceptions = Utils.normalize("Supplies Delivery Shop")

        #"Furniture" is exception only for grouping categories"
        if (self.level < 1):
            self.exceptions += Utils.normalize("Furniture")

    # gets a dictionary of words that appear in categories of a certain sitemap, on a certain level of nesting
    # excluding special categories
    #
    # input: site - sitename as a string 
    #         level - level as an int
    # returns: dictionary indexed by word, with values consisting of the item of that category (from the spider's outputs)
    def words_in_site(self, site):
        # filename is of form "Site/site_categories.jl"
        #filename = site[0].upper() + site[1:] + "/" + site + "_categories.jl"
        filename =  site + "_categories.jl"
        # separate handling for BJs
        # if site.strip() == "bjs":
        #     filename = "BJs/bjs_categories.jl"
        f = codecs.open(filename, "r", "utf-8")

        words = {}
        for line in f:
            item = json.loads(line.strip())
            if int(item['level']) == self.level and 'special' not in item:

                # for every word in category's name (normalized)
                normalized = Utils.normalize(item['text'])

                for word in normalized:
                    # add word to dictionary
                    # value of dictionary is item and site name

                    item["site"] = site
                    # newitem = {}
                    # newitem["site"] = site
                    # newitem["text"] = item["text"]
                    if word not in words:
                        words[word] = [item]
                    else:
                        words[word] = words[word] + [item]
        f.close()
        return words

    # aggregates result of words_in_site to a list of sites, and returns ordered output by the words' frequency
    def words_in_sites(self):
        words = {}
        for site in self.sites:
            site_words = self.words_in_site(site)
            for word in site_words:
                if word not in words:
                    words[word] = site_words[word]
                else:
                    words[word] = words[word] + site_words[word]

        print "\nAll words: "        
        for word in words:
            print Utils.stems[word]
            for item in words[word]:
                print "\t",item["text"].encode("utf-8")
        return sorted(words.items(), key=lambda x: len(x[1]), reverse=True)

    # creates graph that connects words that are both found in a category name
    # to use in grouping function
    # returns connected components of the graph
    def words_graph(self):
        words = nx.Graph()
        for site in self.sites:
            # filename is of form "Site/site_categories.jl"
            #filename = site[0].upper() + site[1:] + "/" + site + "_categories.jl"
            filename = site + "_categories.jl"
            # separate handling for BJs
            # if site.strip() == "bjs":
            #     filename = "BJs/bjs_categories.jl"
            f = codecs.open(filename, "r", "utf-8")

            for line in f:
                item = json.loads(line.strip())
                if int(item['level']) == self.level and 'special' not in item:
                    # every word in category's name (normalized)
                    category_words = Utils.normalize(item['text'])

                    # If category only has one word add it separately as a node
                    if len(category_words) == 1:
                        words.add_node(category_words[0])

                    # add edges between every two words in the name
                    for (word1, word2) in itertools.combinations(category_words,2):

                        # don't add the edge if they are in the exception list
                        if word1 not in self.exceptions:
                            if word2 not in self.exceptions:
                                words.add_edge(word1, word2)

                        # add them as independent nodes if they are not exceptions
                        for word in [word for word in [word1, word2] if word not in self.exceptions]:
                            words.add_node(word)

                        #TODO: not adding them in the graph will cause categories that are composed only of an exception word
                        # ("Supplies", "Delivery") not to appear in the final list of groups at all - I think this is fixed, it's added separately as a node

                        # # instead add them as independent nodes
                        # else:
                        #     words.add_node(word1)
                        #     words.add_node(word2)
            f.close()

        # return the graph
        print "\nWords graph: "
        for sublist in nx.connected_components(words):
            print [Utils.stems[word] for word in sublist]
        return words

    # returns connected components of words graph - output of words_graph()
    def connected_words(self):
        graph = self.words_graph()
        #print nx.connected_components(graph)
        return nx.connected_components(graph)

    # uses words graph to generate groups of words that are connected
    # these will be the connected components of the graph if they are not too large
    # or subgraphs of them based on their cycles
    def connected_words2(self):
        word_graph = self.words_graph()
        #graph = nx.connected_component_subgraphs(graph)[0]

        #TODO: which condition to use?
        #if len(graph.nodes() > 7):

        # for each connected component:
        # if maximum distance between any 2 nodes is <= 4, return connected component
        # otherwise, find cycles and use them + the remaining nodes each with their corresponding cycle
        # (the first node adjacent to it that is in the final components list)
        #TODO: maybe pick the list to which to attach remaining nodes better

        # For grouping lower level categories we allow larger groups
        if (self.level == 1):
            path_limit = 4
        else:
            path_limit = 7

        res_components = []
        for graph in nx.connected_component_subgraphs(word_graph):

            # if connected component's diameter is smaller than limit add it as is

            # get maximum length
            lengths = nx.all_pairs_shortest_path_length(graph)
            m = 0
            for subdict in lengths.itervalues():
                for value in subdict.itervalues():
                    if value > m:
                        m = value

            # if diameter is lower than a limit or there are no cycles (so the else branch wouldn't work)
            if m <= path_limit or not nx.cycle_basis(graph):
                res_components.append(graph.nodes())
            else:
                # else try to remove bridges
                word_groups = []
                subgraphs = nx.cycle_basis(graph)
                # add the remaining nodes
                subgraphs_nodes = [node for subgraph in subgraphs for node in subgraph]
                remaining_nodes = [node for node in graph.nodes() if node not in subgraphs_nodes]

                 # # find largest cycles by building new graph from these cycles and finding connected components - then add the remaining nodes
                 # large_cycles = nx.Graph()
                 # for subgraph in subgraphs:
                 #     for node in subgraph[1:]:
                 #         large_cycles.add_edge(node, subgraph[0])
                 # components = nx.connected_components(large_cycles)
                 components = subgraphs

                # add edges found in the original graph for the remaining nodes
                for node in remaining_nodes:
                    for neighbor in graph.neighbors(node):
                        for component in components:
                            if neighbor in component:
                                component.append(node)
                                break
                res_components += components

        print "\nFinal graph:"
        for sublist in res_components:
            print [Utils.stems[word] for word in sublist]
        return res_components

                #UNDER CONSTRUCTION


    # groups categories by following criteria:
    # all categories in a group contain a word that is found in another category in that group
    # creates graph of words with edges between words that appear in one category name
    # and uses it to group categories that contain that word
    # splits large groups by finding cycles - each cycle along with all direct neighbors of its nodes will form a new group
    # (so one category can be in more than 1 group)
    # returns list of dictionaries of groups containing items as in the spiders' outputs
    def group_by_common_words(self):
        # list containing final category groups
        cat_groups = []
        # connected components of word graph
        word_groups = self.connected_words2()
        # list of categories indexed by words found in them
        sites_words = dict(self.words_in_sites())
        for word_list in word_groups:
            new_group = {"Group_name":"", "Short_name" : "", "Level": self.level, "Group_members":[]}

            # build short name from the full version of the stemmed words in the group's list of words
            #TODO: they shouldn't always be concatenated by "," or "&" (ex: "Home Theater")

            # sort the word list by number of categories the word appears in
            sorted_word_list = sorted(word_list, key=lambda word: len(sites_words[word]))
            short_name = "".join(Utils.stems[sorted_word_list[0]])

            # keep adding words to it until it's above 40 characters
            for word in sorted_word_list[1:]:
                short_name += ", " + Utils.stems[word]#.decode("utf-8")

                # if it's over 40 characters remove the last element and exit loop
                if len(short_name) > 40:
                    short_name = ",".join(short_name.split(",")[:-1])
                    break

            new_group["Short_name"] = short_name

            # build group members list
            names = []
            for word in word_list:
                new_group["Group_members"] = Utils.merge_dictionaries(new_group["Group_members"], sites_words[word], ["site", "text"])

                # construct category name by concatenating all unique category names in the group
                for site_item in sites_words[word]:
                    names.append(site_item["text"])
            cat_name = "; ".join(set(names))
            new_group["Group_name"] = cat_name
            cat_groups.append(new_group)
        return cat_groups


    # group categories and store output in json file
    def serialize(self):
        sites = ["amazon", "bestbuy", "bjs", "bloomingdales", "overstock", "walmart", "wayfair"]
        groups = gc.group_by_common_words()
        f = open('groups.jl', 'wb')
        for group in groups:
            line = json.dumps(group)

            # just extract the 'text' of each element in the group
            line = json.dumps({'Group_members' : map(lambda x: x['text'], group['Group_members'])})

            f.write(line+"\n\n")
        f.close()

    # build categories graph
    #TODO: buggy?
    def cat_graph(self):
        cat_groups = self.group_by_common_words()
        cat_graph = nx.Graph()
        cindex = 0
        for cat_group in cat_groups:
            cindex += 1
            for (cat1, cat2) in itertools.combinations(cat_group["Group_members"],2):
                cat_name = cat1["text"]
                cat_name2 = cat2["text"]
                # handle duplicates - each category name is suffixed by the index of its component
                cat_name = cat_name + str(cindex)
                cat_name2 = cat_name2 + str(cindex)
                cat_graph.add_edge(cat_name,cat_name2)
        return cat_graph

    # build words subgraph of connected components
    def word_graph_connected(self):
        word_subgraph = nx.Graph()
        components = self.connected_words2()
        cindex = 0;
        for component in components:
            cindex += 1
            for (word1, word2) in itertools.combinations(component,2):
                # handle duplicates - each word is suffixed by the index of its component
                word1 = word1 + " " + str(cindex)
                word2 = word2 + " " + str(cindex)
                word_subgraph.add_edge(word1,word2)
                #print word1, word2
        return word_subgraph


if __name__=="__main__":
    sites = ["amazon", "bestbuy", "bjs", "bloomingdales", "overstock", "walmart", "wayfair"]
    sites = ["bjs","bestbuy","walmart","amazon"]
    sites = ["amazon", "walmart"]
    gc = Categories(sites, 1)
    groups = gc.group_by_common_words()
    #pprint(groups)

    #pprint(Utils.stems)

    gc.serialize()

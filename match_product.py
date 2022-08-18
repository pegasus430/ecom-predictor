#!/usr/bin/python

# given two sites and categories/departments, check if there are any common products
# usage:
#        python match_product.py site1 category1 site2 category2 [method (1/2)] [param]

import codecs
import re
import json
import sys
from pprint import pprint
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
import numpy
from numpy import dot
from nltk.corpus import wordnet

def get_products(filename, category):
    output_all = codecs.open(filename, "r", "utf-8")

    products = []

    for line in output_all:
        # print line
        if line.strip():
            item = json.loads(line.strip())
            if 'department' in item:
                if item['department'] == category:
                    products.append(item)
            if 'category' in item:
                if item['category'] == category:
                    products.append(item)

    # close all opened files
    output_all.close()
    return products

# normalize text to list of lowercase words (no punctuation except for inches sign (") or /)
def normalize(orig_text):
    text = orig_text
    # other preprocessing: -Inch = "
    text = re.sub("\-Inch", "\"", text)
    text = re.sub("\-inch", "\"", text)
    #! including ' as an exception keeps things like women's a single word. also doesn't find it as a word in wordnet -> too high a priority
    # excluding it leads to women's->women (s is a stopword)
    text = re.sub("([^\w\"/])|(u')", " ", text)
    stopset = set(stopwords.words('english'))#["and", "the", "&", "for", "of", "on", "as", "to", "in"]
    #tokens = nltk.WordPunctTokenizer().tokenize(text)
    # we need to keep 19" as one word for ex

    #TODO: maybe keep numbers like "50 1/2" together too somehow (originally they're "50-1/2")
    #TODO: maybe handle numbers separately. sometimes we want / to split (in words), and . not to (in numbers)
    # define a better regex above, or here at splitting
    tokens = text.split()
    clean = [token.lower() for token in tokens if token.lower() not in stopset and len(token) > 0]
    #print "clean", orig_text, clean

    return clean

# for a product products1[nrproduct] check if the number of words in common for each of the products in products2
# exceeds a cerain threshold
# weigh non-dictionary words with double weight
# use param to calculate the threshold (0-1) (0.7 or 0.6 is good)
def match(products1, products2, nrproduct, param=0.65):
    product = ''

    product = products1[nrproduct]
    products_found = []

    for product2 in products2:
        product_name = product['product_name']
        product_name2 = product2['product_name']
        # words1 = set(filter(None, re.split("\s", product_name2)))
        # words2 = set(filter(None, re.split("\s", product_name)))
        words1 = set(normalize(product_name))
        words2 = set(normalize(product_name2))
        common_words = words1.intersection(words2)

        weights_common = []
        for word in common_words:
            if not wordnet.synsets(word):
                weights_common.append(2)
            else:
                weights_common.append(1)
        #print common_words, weights_common

        weights1 = []
        for word in words1:
            if not wordnet.synsets(word):
                weights1.append(2)
            else:
                weights1.append(1)

        weights2 = []
        for word in words2:
            if not wordnet.synsets(word):
                weights2.append(2)
            else:
                weights2.append(1)

        #threshold = 0.5*(len(words1) + len(words2))/2

        #print "common words, weight:", common_words, sum(weights_common)

        threshold = param*(sum(weights1) + sum(weights2))/2

        if sum(weights_common) >= threshold:
            products_found.append((product2, sum(weights_common)))
            # product_name += " ".join(list(words1))
            # product_name2 += " ".join(list(words2))
            # print product_name, product_name2
        products_found = sorted(products_found, key = lambda x: x[1], reverse = True)

    return product, products_found


# second approach: rank them with tf-idf, bag of words
# threshold: minimum score (0-1). 0.5-0.65 works good
def match2(products1, products2, nrprod, threshold=0.5):

    product_names1 = [item['product_name'] for item in products1]
    product_names2 = [item['product_name'] for item in products2]

    # use names from both sets to calculate tf-idf
    train_set = product_names1 + product_names2
    # use second set of products to search for best match
    test_set = [product_names1[nrprod]] + product_names2

    stopWords = stopwords.words('english')

    count_vectorizer = CountVectorizer(min_df=1, stop_words=stopWords, analyzer=normalize)
    count_vectorizer.fit_transform(train_set)

    #pprint(count_vectorizer.vocabulary_)

    freq_term_matrix = count_vectorizer.transform(test_set)
    #print freq_term_matrix.todense()

    tfidf = TfidfTransformer(norm="l2")
    tfidf.fit(freq_term_matrix)

    tf_idf_matrix = tfidf.transform(freq_term_matrix)
    tf_idf_matrix = tf_idf_matrix.todense()
    #print tf_idf_matrix

    product = products1[nrprod]
    products_found = []

    index = 0

    # compute tfidf vector for each pair of products and sort them by their dot product
    for product2 in products2:
        index += 1
        v1 = numpy.array(tf_idf_matrix)[0].tolist()
        v2 = numpy.array(tf_idf_matrix)[index].tolist()
        #print dot(v1, v2)

        #TODO: normalize this. cosine similarity?
        #good normalization?
        score = dot(v1,v2)#/(len(product['product_name'])*len(product2['product_name']))

        if score > threshold:
            products_found.append((product2, score))

    # sort products_found by their score
    products_found = sorted(products_found, key = lambda x: x[1], reverse = True)

    return product, products_found


# third approach: check common ngrams (is order important?)

param = 0.65
method = 1

results = 0
site1 = sys.argv[1]
category1 = sys.argv[2]
site2 = sys.argv[3]
category2 = sys.argv[4]
if (len(sys.argv) >= 6):
    method = int(sys.argv[5])
if (len(sys.argv) >= 7):
    param = float(sys.argv[6])

products1 = get_products("sample_output/" + site1 + "_bestsellers_dept.jl", category1)
products2 = get_products("sample_output/" + site2 + "_bestsellers_dept.jl", category2)

for nrprod in range(len(products1)):
    if method == 1:
        (prod, res) = match(products1, products2, nrprod, param)
    if method == 2:
        (prod, res) = match2(products1, products2, nrprod, param)
    if res:
        print "PRODUCT: ", prod['product_name']
        print "MATCHES: "
        for product in res:
            print '-', re.sub("\s+", " ", product[0]['product_name']), "; SCORE:", product[1]
        # for product in res:
        #     print product[0]
        print '--------------------------------'
        results += 1

print "results: ", results
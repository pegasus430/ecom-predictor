#!/usr/bin/python

# Extract phrases that appear frequently in a text (length 2...11)

import re
import nltk
from nltk.util import ngrams
from nltk.corpus import stopwords

import itertools
from collections import Counter
from pprint import pprint

import sys

text = sys.argv[1]

# maximum length of phrases
maxn = 11
#maxn = len(text.split())/2

# extract proper nouns
keywords = []

# eliminate non-word characters and split into sentences
sentences = nltk.sent_tokenize(text)
token_lists = []
for sentence in sentences:

    upper_tokens = nltk.word_tokenize(sentence)
    
    # extract capital letter words that don't occur in the beginning of the sentence
    keywords += [word.lower() for word in upper_tokens[1:] if word[0].isupper()]

    # lowercase
    tokenized = [token.lower() for token in upper_tokens]

    # eliminate punctuation marks
    tokenized = filter(lambda c: not re.match("[\W]",c), tokenized)
    token_lists.append(tokenized)

# stopwords
stopset = set(stopwords.words('english'))

# initialize ngram lists
ngrams_lists = [[] for n in range(2,maxn+1)]

for tokens in token_lists:
    for n in range(2,maxn+1):
        # generate ngrams and eliminate ngrams starting OR ending with a stopword, unless occuring near a keyword, for phrases < 4
        if n < 4:
            ngrams_lists[n-2] += [ngram for ngram in ngrams(tokens, n) \
                if (ngram[0] not in stopset and ngram[-1] not in stopset) \
                or (ngram[0] in keywords or ngram[-1] in keywords)]

        # for phrases > 4 only ignore it if it starts AND ends with a stopword
        else:
            ngrams_lists[n-2] += [ngram for ngram in ngrams(tokens, n) \
                    if (ngram[0] not in stopset or ngram[-1] not in stopset)]

freqs = [Counter(ngrams_list) for ngrams_list in ngrams_lists]

# remove lower level ngrams with lower or equal frequency
for fi in range(maxn,2,-1):
    for (high_ngram, high_count) in freqs[fi-2].items():
        # check (and remove if necessary) all the lower level ngrams
        for fj in range(fi-1,1,-1):
            low_ngrams = freqs[fj-2]
            # generate lower level ngrams
            for low_ngram in zip(*(high_ngram[i:] for i in range(fj))):
                if low_ngrams[low_ngram] <= high_count:
                    del low_ngrams[low_ngram]

# concatenate frequency counters
all_freq = Counter()
for freq in freqs:
    all_freq += freq

# choose ngrams that appear more than once
frequent = [item for item in all_freq.items() if item[1] > 1]

# sort by number of occurences (reverse), then phrase length(reverse), then alphabetically
final = sorted(frequent, key=lambda x: (-x[1], -len(x[0]), x[0]))

# print
for (phrase, frequency) in final:
    print "\"%s\", \"%d\"" % (" ".join(phrase), frequency)
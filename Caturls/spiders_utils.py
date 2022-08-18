import re
import sys

from nltk.util import ngrams
from nltk.corpus import stopwords

__init__=['Utils']

class Utils():
        
    # append domain name in front of relative URL if it's missing
    @staticmethod
    def add_domain(url, root_url):
        if not re.match("https?:.*", url):
            url = root_url + url
        return url

    # clean url of extra parameters, given a list of separators
    # separators must appear as they should appear in a regex (escaped if necessary)
    @staticmethod
    def clean_url(url, separators=['\?',';']):
        for separator in separators:
            m = re.match("([^%s]*)%s.*" % (separator, separator), url)
            if m:
                url = m.group(1)

        return url


    # extract domain from url
    @staticmethod
    def extract_domain(url):
        m = re.match("http://((www1?)|(shop))\.([^\.]+)\.com.*", url)
        if m:
            site = m.group(4)
        else:
            sys.stderr.write('Can\'t extract domain from URL: ' + url + '\n')
            site = None
        return site

    # find frequency of phrases from a text in another text, and density (% of length of text)
    # (will be used with description title and description text)
    @staticmethod
    def phrases_freq(phrases_from, freq_in):
        #TODO: stem?

        stopset = set(stopwords.words('english'))
        ngrams_list = []
        phrases_from_tokens = Utils.normalize_text(phrases_from)
        freq_in = " ".join(Utils.normalize_text(freq_in))
        for l in range(1, len(phrases_from_tokens) + 1):
            for ngram in ngrams(phrases_from_tokens, l):
                # if it doesn't contain only stopwords
                
                # if it doesn't contain any stopwords in the beginning or end
                if ngram[0] not in stopset and ngram[-1] not in stopset:
                    # append as string to the ngram list
                    ngrams_list.append(" ".join(ngram))

        freqs = {}
        for ngram in ngrams_list:
            freqs[ngram] = freq_in.count(ngram)

        # eliminate smaller phrases that are contained in larger ones
        for k in freqs:
            for k2 in freqs:
                if k in k2 and k != k2 and freqs[k] <= freqs[k2]:
                    freqs[k] = 0

        # eliminate zeros
        freqs = dict((k,v) for (k,v) in freqs.iteritems() if v!=0)

        len_text = len(Utils.normalize_text(freq_in))
        density = {}
        for ngram in freqs:
            len_ngram = len(Utils.normalize_text(ngram))
            density[ngram] = format((float(len_ngram)*freqs[ngram])/len_text*100, ".1f")

        return (freqs, density)


    # normalize text to lowercase and eliminate non-word characters.
    # return list of tokens
    @staticmethod
    def normalize_text(text):
        # replace &nbsp with space
        text = re.sub("&nbsp", " ", text)

        # tokenize
        tokens = filter(None, re.split("[^\w\.,]+", text))

        # lowercase and eliminate non-character words. eliminating punctuation marks will make so that matches can cross sentence boundaries & stuff
        #tokens = [re.sub("[^\w,\.?!:]", "", token.lower()) for token in tokens]
        tokens = [re.sub("[^\w]", "", token.lower()) for token in tokens]

        #return " ".join(tokens)
        return tokens

    @staticmethod
    def prettify_html(html_text):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text)
        text = soup.prettify()

        # remove <html> and <body> tags added by prettify
        # only remove first occurence, in case there actually were any in the original text
        text = re.sub("<html> *\n\s*","",text,1)
        text = re.sub("\n *</html>","",text,1)
        text = re.sub("<body> *\n","",text,1)
        text = re.sub("\n *</body>","",text,1)
        return text.encode("utf-8")
#!/usr/bin/python
import re
import nltk
from nltk.corpus import stopwords
from nltk.corpus import wordnet
from string import lower
from scrapy import log
import unicodedata
import itertools
import math
import urllib
import numpy as np
import cv2
from compute_distances import _normalize_image, image_histogram_to_string,\
 compute_histogram, shistogram_similarity, _blockhash, hash_similarity

# process text in product names, compute similarity between products
class ProcessText():
    # weight values
    # value to outweight any theoretical possible threshold. If UPC matches, products should match.
    # TODO: finetune
    UPC_MATCH_WEIGHT = 20
    MANUFACTURER_CODE_MATCH_WEIGHT = 10 # TODO: finetune
    MODEL_MATCH_WEIGHT = 9
    ALT_MODEL_MATCH_WEIGHT = 7
    BRAND_MATCH_WEIGHT = 5
    MEASURE_MATCH_WEIGHT = 3
    NONWORD_MATCH_WEIGHT = 2
    DICTIONARY_WORD_MATCH_WEIGHT = 1
    # if price difference is above this value, consider score penalization
    PRODUCT_PRICE_THRESHOLD = 10
    # threshold to be used if products have no names (independent of names length)
    DEFAULT_THRESH = 12

    # exception brands - are brands names but are also found in the dictionary
    brand_exceptions = ['philips', 'sharp', 'sceptre', 'westinghouse', 'element', 'curtis', 'emerson', 'xerox', 'kellogg']
    # custom stopwords list
    stopwords = ['a', 'an', 'the', 'and', 'or', 'as', 'of', 'at', 'by', \
    'for', 'with', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to', 'from', \
    'up', 'down', 'in', 'on', 'off', 'over', 'under', 'then', 'very']

    # normalize text to list of lowercase words (no punctuation except for inches sign (") or /)
    @staticmethod

    def normalize(orig_text, stem=True, exclude_stopwords=True, lowercase=True):
        text = orig_text

        # first normalize variant of " to " (inches symbol) - found on sony.com (need to do this on unicode version of text or the character will be lost at ascii conversion)
        text = re.sub(u'\u201d', "\"", text, re.UNICODE)

        # convert text to ascii. so accented letters and special characters are all normalized to ascii characters
        # first normalize unicode form
        #TODO: test
        try:
            text = unicodedata.normalize("NFD", unicode(text)).encode("ascii", "ignore")
        except Exception:
            text = unicodedata.normalize("NFD", unicode(text, "utf-8")).encode("ascii", "ignore")


        # other preprocessing: -Inch = " - fitting for staples->amazon search
        #                        Feet = '
        # TODO: suitable for all sites?
        text = re.sub("[- ]*[iI]nch", "\"", text)
        text = re.sub("(?<=[0-9])[iI][nN](?!=c)","\"", text)

        # normalize feet
        text = re.sub("[- ]*[fF]eet", "\'", text)

        # normalize megapixels
        text = re.sub("[- ]*[Mm]egapixels?", "MP", text)

        # normalize Watts
        text = re.sub("[- ]*[Ww]atts?", "W", text)

        # convert yards
        text = re.sub("[- ][yY]ards", "yd", text)

        # convert pack (if it's preceded by space or dash and not followed by a letter)
        text = re.sub("(?<=[- ])[pP]ack(?!([a-z]))", "pk", text)

        # replace w/ with 'with'. note: only lowercase w followd by / and space
        text = re.sub("w/(?= )", "with", text)

        #TODO also do something to match 30x30 with 30"x30"?
        # replace x between numbers (or " or ') with space (usualy a dimension e.g. 11"x30")
        #TODO: what if it's part of a model nu-mber? (maybe not because model numbers are all in caps?)
        #TODO: also match if it starts at beginning of text (^ instead of space)
        text = re.sub("(?<= [0-9\"\'])x(?=[0-9])", " ", text)

        #! including ' as an exception keeps things like women's a single word. also doesn't find it as a word in wordnet -> too high a priority
        # excluding it leads to women's->women (s is a stopword)

        # replace 1/2 by .5 -> suitable for all sites?
        text = re.sub("(?<=[^0-9])[- ]1/2", " 0.5", text)
        text = re.sub("(?<=[0-9])[- ]1/2", ".5", text)
        # also split by "/" after replacing "1/2"

        text = re.sub("u'", " ", text)
        # replace all non-words except for " - . / '
        text = re.sub("[^\w\"\'\-\./]", " ", text)

        # replace - . / if not part of a number - either a number is not before it or is not after it (special case for '-')
        # replace ' if there's not a number before it
        text = re.sub("[\./](?![0-9])", " ", text)
        # replace - with space only if not part of a model number
        # fixes cases like "1-1.2" (will be split into "1 1.2")

        # replace - with space if it's not followed by a number followed by letters or space or the end of the name
        text = re.sub("[\-](?![0-9]+( |$|[a-zA-Z]))", " ", text)
        # replace - with space if it's not preceded by a number (and not followed by a number because of the above)
        text = re.sub("(?<![0-9])[\.\-/\']", " ", text)
        
        tokens = text.split()

        #TODO: remove the len constraint? eg: kellogs k protein

        # only lowercase if flag is set, default is True
        if lowercase:
            clean = [token.lower() for token in tokens]
        else:
            clean = tokens

        if exclude_stopwords:
            ## don't exclude these
            #exceptions = ["t"]
            #stopset = set(stopwords.words('english')).difference(set(exceptions))#["and", "the", "&", "for", "of", "on", "as", "to", "in"]
            stopset = ProcessText.stopwords
            clean = [token for token in clean if token.lower() not in stopset and len(token) > 0]

        # if stemming flag on, also stem words
        #TODO: only if result of stemming is in the dictionary?
        if stem:
            clean = [ProcessText.stem(token) for token in clean]
            clean = [word for word in clean if word != '']

        # TODO:
        # # add versions of the queries with different spelling
        # first add all the tokens but with some words replaced (version of original normalized)
        # extra = []
        # for word_comb in words:
        #     for i in range(len(word_comb)):
        #         # " -> -inch
        #         m = re.match("", string, flags)
        #        # .5 ->  1/2


        return clean


    # return most similar product from a list to a target product (by their names)
    # if none is similar enough, return None
    # arguments:
    #            candidates - list of product items for products to search through, SearchItem objects
    #            param - threshold for accepting a product as similar or not (float between 0-1)
    
    @staticmethod
    def similar(candidates, param):
        result = None
        products_found = []
        for product2 in candidates:

            # origin product features
            product_name = product2['origin_name']
            product_model = product2['origin_model']
            product_price = product2['product_origin_price']
            product_upc = product2['origin_upc']
            product1_mancode = product2['origin_manufacturer_code']
            product_brand = product2['origin_brand']
            try:
                product_image = product2['origin_image_encoded']
            except:
                product_image = None


            words1 = ProcessText.normalize(product_name)
            words2 = ProcessText.normalize(product2['product_name'])
            if 'product_model' in product2:
                product2_model = product2['product_model']
            else:
                product2_model = None

            if 'product_upc' in product2:
                product2_upc = product2['product_upc']
            else:
                product2_upc = None

            if 'manufacturer_code' in product2:
                product2_mancode = product2['manufacturer_code']
            else:
                product2_mancode = None

            if 'product_image_encoded' in product2:
                product2_image = product2['product_image_encoded']
            else:
                product2_image = None

            # and only available for Amazon
            # normalize brand name
            if 'product_brand' in product2:
                product2_brand = " ".join(ProcessText.normalize(product2['product_brand']))

                # ########LOG
                # if product2_brand:
                #     print "BRAND EXTRACTED: ", product2_brand, "FROM URL ", product2['product_url'] 
                # ###########


            else:
                product2_brand = None

            if product_brand:
                product1_brand = " ".join(ProcessText.normalize(product_brand))
            else:
                product1_brand = None


            # compute a term to penalize score woth for large price differences (above 100% of small price)
            # default is 0
            price_score_penalization = 0

            # find (absolute) difference between product prices on each site
            if 'product_target_price' in product2:
                product2_price = float(product2['product_target_price'])

                if product_price:
                    product_price_difference = math.fabs(product_price - product2_price)

                    large_price = max(product_price, product2_price)

                    # compute a score indicating how different product price is on each site (range 0-1)
                    price_score = float(product_price_difference)/large_price

                    # price penalization active for price_score>0.5, calculated by formula:
                    # (price_score*3)^2 (grows quadratically with price difference)

                    # only consider this for product price differnces larger than a constant (10$)
                    #TODO: should I somehow asymptotically make them smaller when difference is smaller instead of omitting them completely?
                    if price_score > 0.5 and product_price_difference > ProcessText.PRODUCT_PRICE_THRESHOLD:
                        price_score_penalization = (price_score * 3) ** 2

                    #print "PRICE SCORE:", price_score_penalization, price_score, product_price, product2_price


            # check if product models match (either from a "Model" field or extracted from their name)
            (model_matched, words1_copy, words2_copy) = ProcessText.models_match(words1, words2, product_model, product2_model)

            # check if product brands match
            (brand_matched, words1_copy, words2_copy) = ProcessText.brands_match(words1_copy, words2_copy, product1_brand, product2_brand)

            # check if product UPCs match
            upc_matched = ProcessText.upcs_match(product_upc, product2_upc)

            # check if manufacturer codes match
            manufacturer_code_matched = ProcessText.manufacturer_code_match(product1_mancode, product2_mancode)

            # compute image similarity score
            if product_image and product2_image:
                image_similarity_score = ProcessText.image_similarity(product_image, product2_image)
            else:
                image_similarity_score = None

            # check if product names match (a similarity score)
            # use copies of brands names with model number replaced with a placeholder
            score = ProcessText.similar_names(words1_copy, words2_copy)

            # add price difference penalization
            score -= price_score_penalization

            # add score for matched brand
            if brand_matched:
                score += ProcessText.BRAND_MATCH_WEIGHT
                log.msg("BRAND MATCHED: " + str(product1_brand) + str(product2_brand) + "\n", level=log.INFO)

            # add score for matched UPC
            if upc_matched:
                score += ProcessText.UPC_MATCH_WEIGHT

            if manufacturer_code_matched:
                score += ProcessText.MANUFACTURER_CODE_MATCH_WEIGHT

            # add model matching score
            if model_matched:
                # only add to score if they have more than a word in common - otherwise assume it's a conincidence model match
                # temporarily remove this condidition to be able to use matching by just model nr and brand (no name)
                # if score > 1:
                # if actual models matched
                if (model_matched == 1):
                    score += ProcessText.MODEL_MATCH_WEIGHT
                # if alternate models matched
                elif (model_matched == 2):
                    score += ProcessText.ALT_MODEL_MATCH_WEIGHT


            # if the products have no product name
            if not words1 or not words2:
                threshold_ = threshold = ProcessText.DEFAULT_THRESH

                log.msg("Default threshold for products with no name", level=log.INFO)
            else:


                # compute threshold for accepting/discarding a match: log(average of name lengths)*10 * parameter
                threshold = param*(math.log(float(len(words1) + len(words2))/2, 10))*10

                # compute confidence of result (using 'threshold' as a landmark - score equal to threshold means 50% confidence)
                # make sure it doesn't exceed 100%
                
                # compute confidence using fixed param of 1.0 (default threshold property). compute threshold for this pair for param=1, and compute confidence.
                # if threshold property (param) will change, spider will accept confidence scores lower than 50 or reject scores higher
                # param_ and threshold_ are local values used only for confidence score computation
                param_ = 1.0
                threshold_ = param_*(math.log(float(len(words1) + len(words2))/2, 10))*10

            if threshold_ != 0:
                confidence = 100 * min(1.0, score/(2.0 * threshold_))
            else:
                log.msg("Threshold was 0 for products: " + str(words1) + "; " + str(words2), level=log.INFO)
                # this means the log in threshold computation above was 0, so products had 1-word names. if anything matched, confidence should be 100%
                confidence = 100.0


            product2['confidence'] = confidence
            product2['UPC_match'] = 1 if upc_matched else 0
            product2['model_match'] = 1 if model_matched else 0


            if score >= threshold:
                # append product along with score and a third variable:
                # variable used for settling ties - aggregating product_matched and brand_matched
                tie_break_score = 0
                if model_matched:
                    tie_break_score += 2
                if brand_matched:
                    tie_break_score += 1
                products_found.append((product2, score, tie_break_score, threshold))


            #### LOGGING
            if 'product_target_price' in product2:
                product2_price = product2['product_target_price']
            else:
                product2_price = ""
            
            try:
                log.msg("\nPRODUCT: " + unicode(product_name) + " URL: " + product2['origin_url'] + " MODEL: " + unicode(product_model) + " PRICE: " + unicode(product_price) + \
                " BRAND: " + unicode(product1_brand) + \
                "\nPRODUCT2: " + unicode(product2['product_name']) + " URL2: " + product2['product_url'] + " BRAND2: " + unicode(product2_brand) + " MODEL2: " + unicode(product2_model) + " PRICE2: " + unicode(product2_price) + \
                "\nSCORE: " + str(score) + " PRICE_PENLZ: " + unicode(price_score_penalization) + " THRESHOLD: " + str(threshold) + \
                "\nIMAGE SIMILARITY: " + str(image_similarity_score) + "\n", level=log.WARNING)
            except:
                log.msg("\nPRODUCT: --Error trying to log product info", level=log.WARNING)

            ###################



        # if score is the same, sort by tie_break_score (indicating if models and/or brands matched),
        # if those are the same, use the threshold (in reverse order of threshold)
        products_found = sorted(products_found, key = lambda x: (x[1], x[2], -x[3]), reverse = True)

        # return most similar product or None
        if products_found:
            result = products_found[0][0]

        return result


    # compute similarity between two products using their product names given as token lists
    # return score
    @staticmethod
    def similar_names(words1, words2):

        common_words = set(words1).intersection(set(words2))
        weights_common = []

        for word in list(common_words):
            weights_common.append(ProcessText.weight(word))

        weights1 = []
        for word in list(set(words1)):
            weights1.append(ProcessText.weight(word))

        weights2 = []
        for word in list(set(words2)):
            weights2.append(ProcessText.weight(word))

        score = sum(weights_common)


        log.msg( "W1: " + str(words1), level=log.INFO)
        log.msg( "W2: " + str(words2), level=log.INFO)
        log.msg( "COMMON: " + str(common_words), level=log.INFO)
        log.msg( "WEIGHTS: " + str(weights1) + str(weights2) + str(weights_common), level=log.INFO)


        return score

    # check if brands of 2 products match, using words in their names, and brand for second product extracted from special field if available
    # return a boolean indicating if brands were matched, and the product names, with matched brands replaced with placeholders
    @staticmethod
    def brands_match(words1, words2, product1_brand, product2_brand):
        # build copies of the original names to use in matching
        words1_copy = list(words1)
        words2_copy = list(words2)

        # treat case with less than 2 words separately

        # if they each have at least 1 word but not 2, append dummy word
        if len(words1_copy) < 2:
            words1_copy.append("__brand1_dummy__")
        if len(words2_copy) < 2:
            words2_copy.append("__brand2_dummy__")

        if product1_brand:
            product1_brand = lower(product1_brand)
        if product2_brand:
            product2_brand = lower(product2_brand)

        # deal with case where actual certain (we're sure these are brands) brands match
        if product1_brand and product2_brand:

            if "".join(product1_brand.split()) == "".join(product2_brand.split()) \
            or set(product1_brand.split()).intersection(set(product2_brand.split())):
                # remove/replace words in brand name
                for word in words1:
                    if word in product1_brand:
                        if "__brand1__" not in words1_copy:
                            words1_copy[words1.index(word)] = "__brand1__"
                        else:
                            words1_copy.remove(word)
                # remove/replace words in brand name
                for word in words2:
                    if word in product2_brand:
                        if "__brand2__" not in words2_copy:
                            words2_copy[words2.index(word)] = "__brand2__"
                        else:
                            words2_copy.remove(word)


                return (True, words1_copy, words2_copy)

            # else:
            #     return (False, words1_copy, words2_copy)

        # deal separately with the case where product2_brand (we're sure this is the brand) is found as is in fist product name
        # check if it's in the concatenation of all words in words1 - this way we capture concatenated pairs of words too.
        # then remove from name only words which were part of product2_brand
        #TODO: does this lead to any errors?
        if product2_brand and "".join(product2_brand.split()) in "".join(words1_copy):
            for word in words1:
                if word in product2_brand:
                    if "__brand1__" not in words1_copy:
                        words1_copy[words1.index(word)] = "__brand1__"
                    else:
                        words1_copy.remove(word)

            for word in words2:
                if word in product2_brand:
                    if "__brand2__" not in words2_copy:
                        words2_copy[words2.index(word)] = "__brand2__"
                    else:
                        words2_copy.remove(word)

            return (True, words1_copy, words2_copy)


        # TODO: maybe do this more optimally - it is a little redundant with the fragment above
        # deal separately with the case where product1_brand (we're sure this is the brand) is found as is in second product name
        # check if it's in the concatenation of all words in words2 - this way we capture concatenated pairs of words too.
        # then remove from name only words which were part of product1_brand
        #TODO: does this lead to any errors?
        if product1_brand and "".join(product1_brand.split()) in "".join(words2_copy):
            # remove/replace words in brand name
            for word in words2:
                if word in product1_brand:
                    if "__brand2__" not in words2_copy:
                        words2_copy[words2.index(word)] = "__brand2__"
                    else:
                        words2_copy.remove(word)

            for word in words1:
                if word in product1_brand:
                    if "__brand1__" not in words1_copy:
                        words1_copy[words1.index(word)] = "__brand1__"
                    else:
                        words1_copy.remove(word)

            return (True, words1_copy, words2_copy)


        # if one product has no words, brand matched is False
        if len(words1_copy) <= 1 or len(words2_copy) <= 1:
            return (False, words1_copy, words2_copy)

        
        brand_matched = False

        # check if brands match - create lists with possible brand names for each of the 2 products, remove matches from word lists
        # (so as not to count twice)

        # add first word, second word, and their concatenation
        brands1 = set([words1_copy[0]])
        # ignore second word if it's a number
        if not ProcessText.is_number(words1_copy[1]):
            brands1.update([words1_copy[1], words1_copy[0] + words1_copy[1]])
        brands2 = set([words2_copy[0]])
        # ignore second word if it's a number
        if not ProcessText.is_number(words2_copy[1]):
            brands2.update([words2_copy[1], words2_copy[0] + words2_copy[1]])
        if product2_brand:
            product2_brand_tokens = product2_brand.split()
            brands2.add(product2_brand_tokens[0])
            if len(product2_brand_tokens) > 1 and not ProcessText.is_number(product2_brand_tokens[1]):
                brands2.update([product2_brand_tokens[1], product2_brand_tokens[0] + product2_brand_tokens[1]])

        # compute intersection of these possible brand names - if not empty then brands match
        intersection_brands = brands1.intersection(brands2)

        # remove matches that were between the second word of each name
        for matched_brand in list(intersection_brands):
            if (matched_brand == words1_copy[1]) \
            and (matched_brand == words2_copy[1]):
                intersection_brands.remove(matched_brand)            

        # if we found a match
        if intersection_brands:
            brand_matched = True
            # consider longest item in the intersection as the matched brand
            # so if a concatenation was matched, use that instead of single words,
            # if a plural was matched, use that instead of singular form
            matched_brand = intersection_brands.pop()

            ## (not in use: - use first match for now - seems to work better. eg: when brand made of 2 words but in second name they are on pos 2 and 3)
            # use longest match as matched brand
            for word in intersection_brands:
                if len(word) > len(matched_brand):
                    matched_brand = word

            # replace matched brand in products names with dummy word (to avoid counting twice)
            if matched_brand in words1_copy:
                words1_copy[words1_copy.index(matched_brand)] = "__brand1__"
            else:
                # this means a concatenation was probably matched (so not present in product name),
                # so try to remove all words from brands1 (could be 2 words)
                for word in brands1:
                    if word in words1_copy and word in matched_brand:
                        # if this is the second word, just remove the word - consider brand as a single word
                        if "__brand1__" not in words1_copy:
                            words1_copy[words1_copy.index(word)] = "__brand1__"
                        else:
                            words1_copy.remove(word)

            if matched_brand in words2_copy:
                words2_copy[words2_copy.index(matched_brand)] = "__brand2__"
            else:
                # this means a concatenation was probably matched (so not present in product name),
                # so try to remove all words from brands2 (could be 2 words)
                for word in brands2:
                    if word in words2_copy and word in matched_brand:
                        # if this is the second word, just remove the word - consider brand as a single word
                        if "__brand2__" not in words2_copy:
                            words2_copy[words2_copy.index(word)] = "__brand2__"
                        else:
                            words2_copy.remove(word)

        return (brand_matched, words1_copy, words2_copy)
    
        
    # check if model numbers of 2 products match
    # return 1 if they match, 2 if they match including alternative model numbers, and 0 if they don't
    # also return copies of the products' names with matched model nrs replaced with placeholders
    @staticmethod
    def models_match(name1, name2, model1, model2):
        # add to the score if their model numbers match
        # check if the product models are the same, or if they are included in the other product's name
        # for the original product models, as well as for the alternative ones, and alternative product names

        # build copies of product names, where matched model will be replaced with a placeholder
        name1_copy = list(name1)
        name2_copy = list(name2)

        alt_product_models = ProcessText.alt_modelnrs(model1)
        alt_product2_models = ProcessText.alt_modelnrs(model2)

        # get product models extracted from product name, if found
        # Obs: product models are also extracted from name inside search spider if explicit product model is not found on page,
        # so this case would be covered, but keep it here as well in case model extraced from page is not the same with model extracted from name (and one of them matches)
        model_index1 = ProcessText.extract_model_nr_index(name1)
        if model_index1 >= 0:
            product_model_fromname = name1[model_index1]
            alt_product_models_fromname = ProcessText.alt_modelnrs(product_model_fromname)
        else:
            product_model_fromname = None
            alt_product_models_fromname = []

        model_index2 = ProcessText.extract_model_nr_index(name2)
        if model_index2 >= 0:
            product2_model_fromname = name2[model_index2]
            alt_product2_models_fromname = ProcessText.alt_modelnrs(product2_model_fromname)
        else:
            product2_model_fromname = None
            alt_product2_models_fromname = []

        model_matched = 0
        # to see if models match, build 2 lists with each of the products' possible models, and check their intersection
        # actual models
        models1 = filter(None, [model1, product_model_fromname])
        models2 = filter(None, [model2, product2_model_fromname])

        # including alternate models
        alt_models1 = filter(None, [model1, product_model_fromname] + alt_product_models + alt_product_models_fromname)
        alt_models2 = filter(None, [model2, product2_model_fromname] + alt_product2_models + alt_product2_models_fromname)

        # normalize all product models
        models1 = map(lambda x: ProcessText.normalize_modelnr(x), models1)
        models2 = map(lambda x: ProcessText.normalize_modelnr(x), models2)
        alt_models1 = map(lambda x: ProcessText.normalize_modelnr(x), alt_models1)
        alt_models2 = map(lambda x: ProcessText.normalize_modelnr(x), alt_models2)

        # if models match
        alt_model_intersection = set(alt_models1).intersection(set(alt_models2))
        model_intersection = set(models1).intersection(set(models2))

        if alt_model_intersection:

            # replace matched model with placeholder
            # (there will only be one modelnr to replace, but try them all cause intersection of alt_models may not be in original names)
            for modelnr in models1:
                if modelnr in name1_copy:
                    name1_copy[name1_copy.index(modelnr)] = "__model1__"
                    break
            for modelnr in models2:
                if modelnr in name2_copy:
                    name2_copy[name2_copy.index(modelnr)] = "__model2__"

            # if actual models match (excluding alternate models)
            if model_intersection:
                
                model_matched = 1
                log.msg("MODEL MATCHED: " + str(models1) + str(models2) + "\n", level=log.INFO)
            # if alternate models match
            else:

                model_matched = 2
                log.msg("ALT MODEL MATCHED: " + str(alt_models1) + str(alt_models2) + "\n", level=log.INFO)
        # if models not matched
        else:
            log.msg("MODEL NOT MATCHED: " + str(alt_models1) + str(alt_models2) + "\n", level=log.INFO)
        
        return (model_matched, name1_copy, name2_copy)

    @staticmethod
    # check if 2 UPCs match
    # can be enirched in the future with more sophisticated checks
    def upcs_match(upc1, upc2):
        # upcs are lists of upcs for each product
        if not upc1 or not upc2:
            log.msg("UPC NOT MATCHED: " + str(upc1) + " " + str(upc2) + "\n", level=log.INFO)
            return False
        if set(upc1).intersection(set(upc2)):
            log.msg("UPC MATCHED: " + str(upc1) + " " + str(upc2) + "\n", level=log.INFO)
            return True
        else:
            log.msg("UPC NOT MATCHED: " + str(upc1) + " " + str(upc2) + " " + str(list(set(upc1).intersection(set(upc2)))) + "\n", level=log.INFO)
            return False

    @staticmethod
    # check if 2 manufacturer codes match
    # can be enirched in the future with more sophisticated checks
    def manufacturer_code_match(code1, code2):
        # upcs are lists of upcs for each product
        if not code1 or not code2:
            log.msg("MANUFACTURER CODE NOT MATCHED: " + str(code1).encode("utf-8") + " " + str(code2).encode("utf-8") + "\n", level=log.INFO)
            return False
        if lower(code1) == lower(code2):
            log.msg("MANUFACTURER CODE MATCHED: " + code1.encode("utf-8") + " " + code2.encode("utf-8") + "\n", level=log.INFO)
            return True
        else:
            log.msg("MANUFACTURER CODE NOT MATCHED: " + code1.encode("utf-8") + " " + code2.encode("utf-8") + "\n", level=log.INFO)
            return False

            

    # check if word is a likely candidate to represent a model number
    @staticmethod
    def is_model_number(word, min_length = 5):
        exceptions = ['skamp', 'skimp']

        # eliminate words smaller than 4 letters (inclusively)
        if len(word) < min_length:
            return False

        word = word.lower()

        # if there are more than 2 numbers and 2 letters and no non-word characters, 
        # assume this is the model number and assign it a higher weight
        letters = len(re.findall("[a-zA-Z]", word))
        vowels = len(re.findall("[aeiouy]", word))
        numbers = len(re.findall("[0-9]", word))

        # some models on bestbuy have a - . but check (was not tested)
        # some models on bestbuy have . or /
        nonwords = len(re.findall("[^\w\-/\.]", word))
        
        if ((letters > 1 and numbers > 0) or numbers > 4 or (numbers >=4 and letters >=1) or\
        (letters > 3 and vowels < 2 and not ProcessText.is_dictionary_word(word))) \
        and word not in exceptions \
        and nonwords==0 \
        and not word.endswith("in") and not word.endswith("inch") and not word.endswith("hz") and \
        not re.match("[0-9]{3,}[kmgt]b", word) and not re.match("[0-9]{3,}p", word) and not re.match("[0-9]{2,}hz", word) \
        and not re.match("[0-9\.]{1,4}oz", word) and not re.match("[0-9\.]{1,4}ml", word)\
        and not re.match("[0-9\.]{1,4}[\-x]{,1}[0-9\.]{1,4}mm", word) and not re.match("[0-9\.]{1,4}m?ah", word):
        # word is not a memory size, frequency(Hz) or pixels description etc
            return True

        return False

    
    # get list of alternative model numbers
    # without the last letters, so as to match more possibilities
    # (there is are cases like this, for example un32eh5300f)
    # or split by dashes
    @staticmethod
    def alt_modelnrs(word):
        alt_models = []
        if not word:
            return []

        # remove last part of word
        m = re.match("(.*[0-9]+)([a-zA-Z\- ]+)$", word)
        if m and float(len(m.group(1)))/len(m.group(2))>1:
            new_word = m.group(1)
            # accept it if it's a model number with at least 4 letters
            if ProcessText.is_model_number(new_word, 4):
                alt_models.append(new_word)

        # split word by - or /
        if "-"  or "/" in word:
            sub_models = re.split(r"[-/]",word)
            for sub_model in sub_models:
                if ProcessText.is_model_number(sub_model.strip()):
                    alt_models.append(sub_model.strip())

        return alt_models

    # normalize model numbers (remove dashes, lowercase)
    @staticmethod
    def normalize_modelnr(modelnr):
        return re.sub("[\- /]", "", modelnr.lower())

    # extract index of (first found) model number in list of words if any
    # return -1 if none found
    @staticmethod
    def extract_model_nr_index(words):
        for i in range(len(words)):
            if ProcessText.is_model_number(words[i]):
                return i
        return -1

    # extract model number from name given as one string in original form (not preprocessed)
    @staticmethod
    def extract_model_from_name(product_name):
        name_tokenized = ProcessText.normalize(product_name, stem=False, exclude_stopwords=False, lowercase=False)
        model_index = ProcessText.extract_model_nr_index(name_tokenized)
        if model_index >= 0:
            return name_tokenized[model_index]
        else:
            return None

    # extract model number from product url, for supported sites
    @staticmethod
    def extract_model_from_url(product_url):
        r = re.match("https?://www1?\.([^/]*)\.com/.*", product_url)
        if not r:
            log.msg("Domain could not be extracted from URL " + product_url + " for extracting product model", level=log.DEBUG)
            return None
        domain = r.group(1)
        # # only walmart is supported
        # if domain not in ['walmart', 'wayfair']:
        #     return None
        
        name_from_url = " ".join(product_url.split("/")[-1].split("-"))
        return ProcessText.extract_model_from_name(name_from_url)


    # compute weight to be used for a word for measuring similarity between two texts
    # assign lower weight to alternative product numbers (if they are, it's indicated by the boolean parameter altModels)
    @staticmethod
    def weight(word):

        if word.endswith("\"") or re.match("[0-9]+\.[0-9]+", word) or re.match("[0-9\.]{1,4}[\-x]{,1}[0-9\.]{1,4}mm", word):
            return ProcessText.MEASURE_MATCH_WEIGHT

        # non dictionary word
        if not ProcessText.is_dictionary_word(word) and not re.match("[0-9]+", word):
            return ProcessText.NONWORD_MATCH_WEIGHT

        # dictionary word
        return ProcessText.DICTIONARY_WORD_MATCH_WEIGHT


    # check if a word is a dictionary word or not
    @staticmethod
    def is_dictionary_word(word):
        if wordnet.synsets(word):
            return True
        return False

    # check if a word is a number (including nr of inches, model nrs (slashes, dashes) etc)
    @staticmethod
    def is_number(word):
        if re.match("[0-9\-\.\"\'\/]+", word):
            return True
        return False

    # return word stemmed of plural mark (if present, else return original word)
    @staticmethod
    def stem(word):
        return re.sub("s$", "", word)


    # create combinations of comb_length words from original text (after normalization and tokenization and filtering out dictionary words)
    # return a list of all combinations
    @staticmethod
    def words_combinations(orig_text, comb_length = 2, fast = False):
        norm_text = ProcessText.normalize(orig_text, stem=False)

        # exceptions to include even if they appear in wordnet
        exceptions = ['nt']

        # only keep non dictionary words
        # also keep Brands that are exceptions
        # keep first word because it's probably the brand
        first_word = norm_text[0]
        #norm_text = [word for word in norm_text[1:] if (not wordnet.synsets(word) or word in exceptions or word in ProcessText.brand_exceptions) and len(word) > 1]
        #norm_text.append(first_word)
        

        # use fast option: don't use combinations, but just first 3 words of the name (works well for amazon)
        if fast:
            words = [norm_text[:3]]
        else:
            combs = itertools.combinations(range(len(norm_text)), comb_length)
            # only select combinations that include first or second word
            words=[map(lambda c: norm_text[c], x) for x in filter(lambda x: 0 in x or 1 in x, list(combs))]

        # keep only unique sets of words (regardless of order), eliminate duplicates from each list
        # use tuples because they are hashable (to put them in a set), then convert them back to lists
        return map(lambda x: list(x), list(set(map(lambda x: tuple(set(sorted(x))), words))))

    @staticmethod
    def _url_to_image(url):
        # download the image, convert it to a NumPy array, and then read
        # it into OpenCV format
        resp = urllib.urlopen(url)
        image = np.asarray(bytearray(resp.read()), dtype="uint8")
        image = cv2.imdecode(image, cv2.IMREAD_COLOR)
        return image

    @staticmethod
    def encode_image(url):
        '''Input an image url
        Encode the image as a string and return it
        The string will contain the image histogram, encoded as a string,
        and the image blockhash, encoded as a string; separated by space
        '''
        image = ProcessText._url_to_image(url)
        image = _normalize_image(image)
        histstr = image_histogram_to_string(image, equalize=False)
        bhash = _blockhash(image)

        code = " ".join([histstr, bhash])
        return code

    @staticmethod
    def image_similarity(encoded_im1, encoded_im2, hist_weight=0.8):
        '''Take as input 2 encoded images (as encoded by encode_image above),
        compute their similarities
        :param hist_weight: weight of histogram similarity vs hash similarity
        '''

        hist1, hash1 = encoded_im1.split()
        hist2, hash2 = encoded_im2.split()

        hist_sim = shistogram_similarity(hist1, hist2)
        hash_sim = hash_similarity(hash1, hash2)

        hash_weight = 1 - hist_weight

        score = hist_weight * hist_sim + hash_weight * hash_sim
        return score
# -*- coding: utf-8 -*-

import re

import dateparser

from amazon import AmazonReviewSpider


class AmazonFrReviewSpider(AmazonReviewSpider):

    retailer = 'amazon_fr'

    host = 'www.amazon.fr'

    stop_words = {'alors', 'aucuns', 'aussi', 'autre', 'avant', 'avec',
                  'avoir', 'bon', 'car', 'cela', 'ces', 'ceux', 'chaque',
                  'comme', 'comment', 'dans', 'des', 'dedans', 'dehors',
                  'depuis', 'devrait', 'doit', 'donc', 'dos', u'début', 'elle',
                  'elles', 'encore', 'essai', 'est', 'fait', 'faites', 'fois',
                  'font', 'hors', 'ici', 'ils', 'juste', 'les', 'leur',
                  'maintenant', 'mais', 'mes', 'mine', 'moins', 'mon', 'mot',
                  u'même', u'nommés', 'notre', 'nous', 'par', 'parce', 'pas',
                  'peut', 'peu', 'plupart', 'pour', 'pourquoi', 'quand', 'que',
                  'quel', 'quelle', 'quelles', 'quels', 'qui', 'sans', 'ses',
                  'seulement', 'sien', 'son', 'sont', 'sous', 'soyez', 'sujet',
                  'sur', 'tandis', 'tellement', 'tels', 'tes', 'ton', 'tous',
                  'tout', 'trop', u'très', 'voient', 'vont', 'votre', 'vous',
                  u'étaient', u'état', u'étions', u'été', u'être'}

    def _parse_date(self, review_html):
        date = review_html.xpath(".//*[@data-hook='review-date']/text()")
        if date:
            return dateparser.parse(date[0], ['le %d %B %Y'], ['fr'])

    def _parse_rating(self, review_html):
        rating = review_html.xpath(".//*[@data-hook='review-star-rating']/span/text()")
        if rating:
            stars = re.match(r'(\d),0', rating[0])
            if stars:
                return int(stars.group(1))

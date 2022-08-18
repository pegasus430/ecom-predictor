# -*- coding: utf-8 -*-
import re
import json
from collections import namedtuple
from scrapy import FormRequest, Field, Item, Request
from product_ranking.spiders import BaseProductsSpider


class InstagramUsersItem(Item):
    username = Field()
    followers = Field()
    total_posts = Field()
    posts = Field()

    # Search metadata.
    site = Field()  # String.
    search_term = Field()  # String.
    ranking = Field()  # Integer.
    total_matches = Field()  # Integer.
    results_per_page = Field()  # Integer.
    scraped_results_per_page = Field()  # Integer.
    search_term_in_title_exactly = Field()
    search_term_in_title_partial = Field()
    search_term_in_title_interleaved = Field()
    _statistics = Field()


class InstagramCrawlerSpider(BaseProductsSpider):
    name = "instagram_users_products"
    allowed_domains = ["instagram.com"]
    posts_url = 'https://www.instagram.com/query/'

    def __init__(self, *args, **kwargs):
        super(InstagramCrawlerSpider, self).__init__(
            site_name="instagram.com",
            *args, **kwargs)
        self.product_url = kwargs['product_url']

        self.comments = []
        self.likes = []
        self.num_pages = 1

    @staticmethod
    def valid_url(url):
        if not re.findall(r"http(s){0,1}\:\/\/", url):
            url = "http://" + url
        return url

    def start_requests(self):
        yield Request(url=self.valid_url(self.product_url),
                      meta={'remaining': 99999,
                            'search_term': ''},
                      callback=self._parse_single_product)

    def _parse_single_product(self, response):
        # extracting json data from <script>
        javascript = "".join(response.xpath(
            '//script[contains(text(), "sharedData")]/text()'
        ).extract())
        json_data = json.loads("".join(re.findall(
            r'window._sharedData = (.*);', javascript)))

        item = InstagramUsersItem()
        data = json_data.get("entry_data").get("ProfilePage")[0]
        user = data.get('user')
        media = user.get("media")
        user_id = user.get('id')
        item["username"] = user.get("username")
        item["followers"] = user.get("followed_by").get("count")
        item["total_posts"] = media.get("count")
        # csrf token is required for /query request
        csrf_token = json_data.get('config').get('csrf_token')
        q_post_parameter = self._query_string(user_id)

        # dicts required for /query
        formdata = {'q': q_post_parameter, 'ref': 'users::show'}
        cookies = {'csrftoken': csrf_token}
        headers = {'X-Instagram-AJAX': '1',
                   'X-CSRFToken': csrf_token,
                   'X-Requested-With': 'XMLHttpRequest',
                   'Referer': response.url,
                   'Content-Type': 'application/x-www-form-urlencoded'}

        request = FormRequest(self.posts_url, method='POST',
                              callback=self._parse_posts,
                              cookies=cookies,
                              formdata=formdata,
                              headers=headers)
        request.meta['item'] = item
        request.meta['headers'] = headers
        request.meta['formdata'] = formdata
        request.meta['user_id'] = user_id
        yield request

    def _parse_posts(self, response):
        """extracting amount of likes and comments"""
        item = response.meta.get('item')
        data = json.loads(response.body_as_unicode())
        posts = data.get('media').get('nodes')
        page_info = data.get('media').get('page_info')

        for post in posts:
            count_comments = post.get('comments').get('count')
            count_likes = post.get('likes').get('count')
            self.comments.append(count_comments)
            self.likes.append(count_likes)

        if page_info.get('has_next_page'):
            headers = response.meta.get('headers')
            end_cursor = page_info.get('end_cursor')
            user_id = response.meta.get('user_id')
            formdata = response.meta.get('formdata')
            formdata['q'] = self._query_string(user_id,
                                              end_cursor)
            request = FormRequest(self.posts_url,
                                  method='POST',
                                  callback=self._parse_posts,
                                  formdata=formdata,
                                  headers=headers)
            request.meta['item'] = item
            request.meta['headers'] = headers
            request.meta['formdata'] = formdata
            request.meta['user_id'] = user_id
            yield request
        else:
            post = namedtuple('Post', ['comments', 'likes'])
            item['posts'] = [post(*element) for element in zip(self.comments, self.likes)]
            yield item

    @staticmethod
    def _query_string(user_id, end_cursor=False):
        """q (POST) parameter"""
        if end_cursor:
            return """ig_user(%s) { media.after(%s, 500) {
                count,
                nodes {
                  comments {
                    count
                  },
                  likes {
                    count
                  }
                },
                page_info
              }
               }""" % (user_id, end_cursor)
        else:
            return """ig_user(%s) { media.first(1) {
                  count,
                  nodes {
                    comments {
                      count
                    },
                    likes {
                      count
                    }
                  },
                  page_info
                }
                 }""" % user_id

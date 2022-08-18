import math
from itertools import islice

from flask import request


class Paginate(object):

    def __init__(self, items, per_page, count=None):
        page = request.args.get('page', 1)

        try:
            self.page = int(page)
        except:
            self.page = 1

        self.per_page = per_page

        if count is None:
            count = items.count()

        self.count = count

        self.pages = int(math.ceil(self.count/float(per_page)))

        if self.page > self.pages:
            self.page = self.pages

        if self.page < 1:
            self.page = 1

        if self.page < self.pages:
            self.has_next = True
            self.next_num = self.page + 1
        else:
            self.has_next = False

        if self.page > 1:
            self.has_prev = True
            self.prev_num = self.page - 1
        else:
            self.has_prev = False

        if hasattr(items, '__getitem__'):
            self.items = items[(self.page - 1) * self.per_page:self.page * self.per_page]
        else:
            self.items = islice(items, (self.page - 1) * self.per_page, self.page * self.per_page)

    def iter_pages(self):
        last = 0

        for num in xrange(1, self.pages + 1):
            if num <= 2 or (self.page - 3 < num < self.page + 5) or num > self.pages - 2:
                if last + 1 != num:
                    yield None
                yield num
                last = num

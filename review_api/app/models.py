
class Item(dict):

    def __init__(self, *args, **kwargs):
        if hasattr(self, 'fields'):
            for field in self.fields:
                self[field] = kwargs.pop(field, None)

        super(Item, self).__init__(*args, **kwargs)


class Review(Item):

    fields = [
        'product_id',
        'product_url',
        'product_name',
        'date',
        'url',
        'rating',
        'author_name',
        'author_profile',
        'title',
        'text'
    ]


class Task(Item):

    fields = [
        'started_at',
        'ended_at',
        'retailer',
        'product_id',
        'product_url',
        'group_id',
        'message',
        'server',
        'from_date',
        'reviews',
        'reviews_by_rating',
        'notify_email'
    ]


class DailyTask(Item):

    fields = [
        'last_run_at',
        'frequency',
        'retailer',
        'product_id',
        'product_url',
        'group_id',
        'server',
        'from_date',
        'notify_email'
    ]


class Alert(Item):

    fields = [
        'retailer',
        'product_id',
        'notify_email'
    ]

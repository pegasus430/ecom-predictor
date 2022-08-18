# -*- coding: utf-8 -*-#
"""
Here will be functions for amazon's spiders, for modularity architecture.
"""


def build_categories(product):
    key = "category"
    category = list(product.get(key, []))
    if not category:
        return
    min_category = category.pop(0)
    for cat in category:
        if min_category.get("rank") > cat.get("rank"):
            min_category = cat
        elif min_category.get("rank") == cat.get("rank"):
            if len(min_category.get(key)) < len(cat.get(key)):
                min_category = cat
    categories = min_category.get("category", "").split(">")
    if categories:
        product["categories"] = [x.strip() for x in categories]
    del product[key]
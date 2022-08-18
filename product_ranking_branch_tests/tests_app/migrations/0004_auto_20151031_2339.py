# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0003_remove_spider_active'),
    ]

    operations = [
        migrations.AlterField(
            model_name='spider',
            name='searchterms',
            field=models.ManyToManyField(help_text=b'Choose at least 3.', to='tests_app.SearchTerm'),
        ),
        migrations.AlterField(
            model_name='testrun',
            name='exclude_fields',
            field=multiselectfield.db.fields.MultiSelectField(blank=True, max_length=838, null=True, choices=[(b'search_term_in_title_partial', b'search_term_in_title_partial'), (b'marketplace', b'marketplace'), (b'last_buyer_review_date', b'last_buyer_review_date'), (b'_walmart_current_id', b'_walmart_current_id'), (b'locale', b'locale'), (b'site', b'site'), (b'date_of_last_question', b'date_of_last_question'), (b'price_original', b'price_original'), (b'_walmart_original_id', b'_walmart_original_id'), (b'results_per_page', b'results_per_page'), (b'is_single_result', b'is_single_result'), (b'search_term', b'search_term'), (b'not_found', b'not_found'), (b'deliver_in', b'deliver_in'), (b'category', b'category'), (b'title', b'title'), (b'_walmart_original_oos', b'_walmart_original_oos'), (b'google_source_site', b'google_source_site'), (b'_subitem', b'_subitem'), (b'limited_stock', b'limited_stock'), (b'sku', b'sku'), (b'department', b'department'), (b'price', b'price'), (b'related_products', b'related_products'), (b'ranking', b'ranking'), (b'search_term_in_title_exactly', b'search_term_in_title_exactly'), (b'description', b'description'), (b'is_pickup_only', b'is_pickup_only'), (b'no_longer_available', b'no_longer_available'), (b'brand', b'brand'), (b'_statistics', b'_statistics'), (b'buyer_reviews', b'buyer_reviews'), (b'recent_questions', b'recent_questions'), (b'shelf_path', b'shelf_path'), (b'sponsored_links', b'sponsored_links'), (b'variants', b'variants'), (b'is_out_of_stock', b'is_out_of_stock'), (b'is_mobile_agent', b'is_mobile_agent'), (b'price_subscribe_save', b'price_subscribe_save'), (b'categories', b'categories'), (b'prime', b'prime'), (b'special_pricing', b'special_pricing'), (b'shelf_name', b'shelf_name'), (b'url', b'url'), (b'total_matches', b'total_matches'), (b'response_code', b'response_code'), (b'assortment_url', b'assortment_url'), (b'upc', b'upc'), (b'shipping', b'shipping'), (b'_walmart_original_price', b'_walmart_original_price'), (b'is_in_store_only', b'is_in_store_only'), (b'scraped_results_per_page', b'scraped_results_per_page'), (b'image_url', b'image_url'), (b'search_term_in_title_interleaved', b'search_term_in_title_interleaved'), (b'_walmart_redirected', b'_walmart_redirected'), (b'shelf_page_out_of_stock', b'shelf_page_out_of_stock'), (b'model', b'model'), (b'bestseller_rank', b'bestseller_rank')]),
        ),
    ]

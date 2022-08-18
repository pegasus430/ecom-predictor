# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('tests_app', '0005_auto_20151031_2340'),
    ]

    operations = [
        migrations.AddField(
            model_name='report',
            name='searchterm',
            field=models.ForeignKey(related_name='searchterm_reports', default=1, to='tests_app.SearchTerm'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='testrun',
            name='exclude_fields',
            field=multiselectfield.db.fields.MultiSelectField(blank=True, max_length=838, null=True, choices=[(b'_statistics', b'_statistics'), (b'_subitem', b'_subitem'), (b'_walmart_current_id', b'_walmart_current_id'), (b'_walmart_original_id', b'_walmart_original_id'), (b'_walmart_original_oos', b'_walmart_original_oos'), (b'_walmart_original_price', b'_walmart_original_price'), (b'_walmart_redirected', b'_walmart_redirected'), (b'assortment_url', b'assortment_url'), (b'bestseller_rank', b'bestseller_rank'), (b'brand', b'brand'), (b'buyer_reviews', b'buyer_reviews'), (b'categories', b'categories'), (b'category', b'category'), (b'date_of_last_question', b'date_of_last_question'), (b'deliver_in', b'deliver_in'), (b'department', b'department'), (b'description', b'description'), (b'google_source_site', b'google_source_site'), (b'image_url', b'image_url'), (b'is_in_store_only', b'is_in_store_only'), (b'is_mobile_agent', b'is_mobile_agent'), (b'is_out_of_stock', b'is_out_of_stock'), (b'is_pickup_only', b'is_pickup_only'), (b'is_single_result', b'is_single_result'), (b'last_buyer_review_date', b'last_buyer_review_date'), (b'limited_stock', b'limited_stock'), (b'locale', b'locale'), (b'marketplace', b'marketplace'), (b'model', b'model'), (b'no_longer_available', b'no_longer_available'), (b'not_found', b'not_found'), (b'price', b'price'), (b'price_original', b'price_original'), (b'price_subscribe_save', b'price_subscribe_save'), (b'prime', b'prime'), (b'ranking', b'ranking'), (b'recent_questions', b'recent_questions'), (b'related_products', b'related_products'), (b'response_code', b'response_code'), (b'results_per_page', b'results_per_page'), (b'scraped_results_per_page', b'scraped_results_per_page'), (b'search_term', b'search_term'), (b'search_term_in_title_exactly', b'search_term_in_title_exactly'), (b'search_term_in_title_interleaved', b'search_term_in_title_interleaved'), (b'search_term_in_title_partial', b'search_term_in_title_partial'), (b'shelf_name', b'shelf_name'), (b'shelf_page_out_of_stock', b'shelf_page_out_of_stock'), (b'shelf_path', b'shelf_path'), (b'shipping', b'shipping'), (b'site', b'site'), (b'sku', b'sku'), (b'special_pricing', b'special_pricing'), (b'sponsored_links', b'sponsored_links'), (b'title', b'title'), (b'total_matches', b'total_matches'), (b'upc', b'upc'), (b'url', b'url'), (b'variants', b'variants')]),
        ),
        migrations.AlterUniqueTogether(
            name='report',
            unique_together=set([('testrun', 'searchterm')]),
        ),
    ]

from rest_framework import serializers
from walmart_api.models import RichMediaMarketingContent

CHOICES = [
    "https://marketplace.walmartapis.com/v2/feeds?feedType=item",
    "https://marketplace.walmartapis.com/v3/feeds?feedType=SUPPLIER_FULL_ITEM"
]
FEED_CHOICES = [
    "https://marketplace.walmartapis.com/v2/feeds/{feedId}?includeDetails=true",
    "https://marketplace.walmartapis.com/v3/feeds/{feedId}?includeDetails=true"
]


class StringListField(serializers.ListField):
    child = serializers.CharField()


class WalmartApiItemsWithXmlFileRequestSerializer(serializers.Serializer):
    server_name = serializers.CharField(initial="rest_api_web_interface")
    consumer_id = serializers.CharField(allow_blank=True)
    private_key = serializers.CharField(allow_blank=True)
    request_url = serializers.ChoiceField(initial=CHOICES[1], choices=CHOICES)
    request_method = serializers.ChoiceField(choices=["POST"])
    xml_file_to_upload = serializers.FileField(style={'template': 'multiple_file_field.html'})
    submit_as_one_xml_file = serializers.BooleanField(
        initial=False,
        style={'template': 'checkbox_next_to_submit_button.html'}
    )

    """
    There can be also the code below (our backend supports this):
    request_url_2 = serializers.ChoiceField(choices=["https://marketplace.walmartapis.com/v2/feeds?feedType=item"])
    request_method_2 = serializers.ChoiceField(choices=["POST"])
    xml_file_to_upload_2 = serializers.FileField(style={'template': 'multiple_file_field.html'})
    request_url_3 = serializers.ChoiceField(choices=["https://marketplace.walmartapis.com/v2/feeds?feedType=item"])
    request_method_3 = serializers.ChoiceField(choices=["POST"])
    xml_file_to_upload_3 = serializers.FileField(style={'template': 'multiple_file_field.html'})
    """


class WalmartApiItemsWithXmlTextRequestSerializer(serializers.Serializer):
    request_url = serializers.ChoiceField(choices=["https://marketplace.walmartapis.com/v2/feeds?feedType=item"])
    request_method = serializers.ChoiceField(choices=["POST"])
    xml_content_to_upload = serializers.CharField(style={'base_template': 'textarea.html'})


class WalmartApiFeedRequestSerializer(serializers.Serializer):
    request_url = serializers.ChoiceField(choices=FEED_CHOICES)
    feed_id = serializers.CharField()
    request_url_2 = serializers.ChoiceField(choices=FEED_CHOICES)
    feed_id_2 = serializers.CharField()
    request_url_3 = serializers.ChoiceField(choices=FEED_CHOICES)
    feed_id_3 = serializers.CharField()


class WalmartApiValidateXmlTextRequestSerializer(serializers.Serializer):
    xml_content_to_validate = serializers.CharField(style={'base_template': 'textarea.html'})


class WalmartApiValidateXmlFileRequestSerializer(serializers.Serializer):
    xml_file_to_validate = serializers.FileField(style={'template': 'multiple_file_field.html'})
    """
    xml_file_to_validate_2 = serializers.FileField()
    xml_file_to_validate_3 = serializers.FileField()
    """


class WalmartDetectDuplicateContentRequestSerializer(serializers.Serializer):
    product_url_1 = serializers.CharField()
    product_url_2 = serializers.CharField()
    product_url_3 = serializers.CharField()
    product_url_4 = serializers.CharField()
    product_url_5 = serializers.CharField()

    detect_duplication_in_sellers_only = serializers.BooleanField(
        initial=False,
        style={'template': 'checkbox_next_to_submit_button.html'}
    )


class WalmartDetectDuplicateContentFromCsvFileRequestSerializer(serializers.Serializer):
    csv_file_to_check = serializers.FileField()


class CheckItemStatusByProductIDSerializer(serializers.Serializer):
    numbers = serializers.CharField(max_length=2000, style={'base_template': 'textarea.html'})


class ToolIDSerializer(serializers.Serializer):
    api_key = serializers.CharField()
    upcs = serializers.CharField(style={'base_template': 'textarea.html'})
    detailed = serializers.BooleanField(default=False)


class ListItemsWithErrorSerializer(serializers.Serializer):
    as_excel = serializers.BooleanField(default=False)
    page = serializers.IntegerField(min_value=1, initial=1, style={'input_type': 'hidden', 'hide_label': True})


class RichMediaSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(
        choices=['REPLACE', 'MERGE', 'DELETE'])

    item_id = serializers.IntegerField(initial="0")

    marketing_content = serializers.CharField(
        style={'template': 'rich_textarea.html'},
        initial=lambda: getattr(RichMediaMarketingContent.objects.all().first(), 'marketing_content', ''))


class FeedDetailsSerializer(serializers.Serializer):
    request_url = serializers.ChoiceField(choices=FEED_CHOICES)
    feed_id = serializers.CharField()
    as_excel = serializers.BooleanField(
        default=False,
        style={'is_hidden': True, 'template': 'rest_framework/custom_fields/hideable_checkbox.html'}
    )

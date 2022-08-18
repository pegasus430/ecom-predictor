from rest_framework import serializers


class StringListField(serializers.ListField):
    child = serializers.CharField()


class ImageUrlSerializer(serializers.Serializer):
    urls = StringListField()
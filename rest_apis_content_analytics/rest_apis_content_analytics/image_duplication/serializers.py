from rest_framework import serializers


class StringListField(serializers.ListField):
    child = serializers.CharField()


class ImageUrlSerializer(serializers.Serializer):
    urls = StringListField()
#    rate = serializers.FloatField()


class CompareTwoImageListsSerializer(serializers.Serializer):
    urls1 = StringListField()
    urls2 = StringListField()
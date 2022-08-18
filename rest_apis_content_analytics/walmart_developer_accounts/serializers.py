from models import Account
from rest_framework import serializers


class WalmartDevAccountSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Account
        fields = ('name', "api_key")

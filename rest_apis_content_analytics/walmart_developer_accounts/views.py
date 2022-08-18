from django.shortcuts import render
from models import Account
from serializers import WalmartDevAccountSerializer
from rest_framework import viewsets

# Create your views here.

class WalmartAccountViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = Account.objects.all()
    serializer_class = WalmartDevAccountSerializer

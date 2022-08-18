from django.db import models

# Create your models here.

class Account(models.Model):
    name = models.CharField(max_length=200, unique=True)
    api_key = models.CharField(max_length=200)

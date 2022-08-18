# Auth needs a Django Auth Model User
# Create a dummy one if not exists
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Create a dummy user for auth'

    def handle(self, *args, **options):
        try:
            User.objects.get(username='dummy')
            print "Dummy user already exist"

        except User.DoesNotExist:
            user = User()
            user.username = 'dummy'
            user.save()
            print "Created new dummy user"
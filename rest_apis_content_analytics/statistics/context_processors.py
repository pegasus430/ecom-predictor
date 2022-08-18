import datetime

from django.conf import settings
from django.core.cache import cache

from .models import SubmitXMLItem
from walmart_api.utils import get_stats_cache_key_for_request_or_user


def _filter_qs_by_date(qs, field_name, date):
    args = {
        field_name+'__year': date.year,
        field_name+'__month': date.month,
        field_name+'__day': date.day
    }
    return qs.filter(**args)


def _failed_xml_items(user):
    return SubmitXMLItem.objects.filter(user=user, status='failed').order_by('-when').distinct()


def _successful_xml_items(user):
    return SubmitXMLItem.objects.filter(user=user, status='successful').order_by('-when').distinct()


def _today_all_xml_items(user):
    return _filter_qs_by_date(
        SubmitXMLItem.objects.filter(user=user),
        'when', datetime.datetime.today()
    ).order_by('-when').distinct()


def _today_successful_xml_items(user):
    return _filter_qs_by_date(
        SubmitXMLItem.objects.filter(user=user, status='successful'),
        'when', datetime.datetime.today()
    ).order_by('-when').distinct()


def stats_walmart_xml_items(request_or_user, delete_old_cache=False, generate_cache=False):
    if hasattr(request_or_user, 'user') and hasattr(request_or_user.user, 'is_authenticated'):
        user = request_or_user.user
    else:
        user = request_or_user

    if not user.is_authenticated():
        return {}

    cache_key = get_stats_cache_key_for_request_or_user(user)

    cached_data = cache.get(cache_key) if cache_key else None
    if cached_data and cache_key:
        return cached_data

    if not generate_cache:
        return {}  # do not return anything by default

    result = {
        'stats_all_walmart_xml_items': SubmitXMLItem.objects.filter(user=user).order_by('-when').distinct().count(),
        'stats_failed_walmart_xml_items': _failed_xml_items(user).count(),
        'stats_successful_walmart_xml_items': _successful_xml_items(user).count(),
        'stats_today_all_xml_items': _today_all_xml_items(user).count(),
        'stats_today_successful_xml_items': _today_successful_xml_items(user).count(),
    }

    if delete_old_cache:
        cache.delete(cache_key)

    cache.set(cache_key, result, timeout=60*10)

    return result

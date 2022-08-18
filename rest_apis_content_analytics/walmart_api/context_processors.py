import json

from django.core.cache import cache
from django.conf import settings

from walmart_api.utils import get_submission_history_cache_key_for_request_or_user
from .models import SubmissionHistory


def _get_submission_history(request_or_user):
    if hasattr(request_or_user, 'user'):  # we got request
        if request_or_user.user.is_authenticated():
            return SubmissionHistory.objects.filter(user=request_or_user.user)
    else:  # we got user
        return SubmissionHistory.objects.filter(user=request_or_user)


def get_submission_history_as_json(request_or_user, delete_old_cache=False, generate_cache=False):
    cache_key = get_submission_history_cache_key_for_request_or_user(request_or_user)

    cached_data = cache.get(cache_key) if cache_key else None
    if cached_data and cache_key:
        return {'submission_history_as_json': cached_data}

    if not generate_cache:
        return {'submission_history_as_json': None}

    subm_history = _get_submission_history(request_or_user)
    if not subm_history:
        return {}
    result = json.dumps({
        s.feed_id: {'all_statuses': s.get_statuses(), 'ok': s.all_items_ok()}
        for s in subm_history
    })

    if delete_old_cache:
        cache.delete(cache_key)

    cache.set(cache_key, result, timeout=60*10)

    return {'submission_history_as_json': result}
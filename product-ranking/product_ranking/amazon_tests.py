from product_ranking.validation import BaseValidator


class AmazonTests(BaseValidator):
    """docstring for AmazonTests"""

    def _validate_url(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 1500:  # too long
            return False
        if val.strip().count(u' ') > 5:  # too many spaces
            return False
        if not val.strip().lower().startswith('http'):
            return False
        return True

    def _validate_image_url(self, val):
        if not bool(val.strip()):  # empty
            return False
        if val.strip().count(u' ') > 5:  # too many spaces
            return False
        if not val.strip().lower().startswith(('http', 'data:image')):
            return False
        return True

    def _validate_title(self, val):
        if not bool(val.strip()):  # empty
            return False
        if len(val.strip()) > 2500:  # too long
            return False
        if val.strip().count(u' ') > 600:  # too many spaces
            return False
        if '<' in val or '>' in val:  # no tags
            return False    
        return True
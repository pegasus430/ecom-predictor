curl "http://unilever.com/brands-in-action/view-brands.aspx?view=AtoZ" 2>/dev/null| \
grep "span class=\"title\"" | \
python -c "import sys; source=sys.stdin.read(); import re; names=re.findall('span class=.title.>([^<>]+)<', source); from pprint import pprint; print repr(names).decode('unicode_escape').encode('utf-8')"
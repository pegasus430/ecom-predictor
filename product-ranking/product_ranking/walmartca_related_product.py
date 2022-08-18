# coding=utf-8

import urllib
import re

is_empty = lambda x, y="": x[0] if x else y

def _is_none(arg):
    if arg is None:
        arg = ''
    return arg

def init_params(self):
    default_value = None
    attributes = ['session_id', 'view_guid', 'placement_types', 'user_id',
                  'segments', 'clickthru_server', 'image_server', 'added_to_cart_item_ids',
                  'json_enabled', 'landing_page_id', 'cart_value', 'listen_mode_forced',
                  'forced_strategies', 'forced_treatment', 'forced_campaign', 'ip_override',
                  'rap', 'forced_ftp', 'from_rich_mail', 'category_hint_ids',
                  'locale', 'brand', 'uids', 'clearance_page', 'filter_brands',
                  'filter_brands_include', 'filter_categories', 'filter_categories_include',
                  'filter_price_cents_min', 'filter_price_cents_max', 'filter_price_min',
                  'filter_price_max', 'filter_price_include', 'clickthru_params', 'region_id',
                  'filters', 'refinements', 'rad', 'rad_level', 'promo_campaign_id',
                  'promo_placement_type', 'promo_creative_id', 'registry_type', 'spoof',
                  'search_terms', 'registry_id', 'immediate_callback_forced', 'json_callback',
                  'blocked_item_ids', 'item_ids', 'display_mode_forced', 'debug_mode',
                  'dummy_data_used', 'dev_mode_forced', 'top_level_genre', 'categories',
                  'category_ids', 'name', 'description', 'image_id', 'link_id',
                  'release_date', 'cents', 'dollars_and_cents', 'sale_dollars_and_cents',
                  'sale_cents', 'price', 'sale_price', 'rating', 'end_date',
                  'recommendable', 'attributes', 'in_stock']
    for attr in attributes:
        setattr(self, attr, default_value)

class R3Common(object):

    def __init__(self, rr_entity):
        # ---------------------------
        init_params(self)
        # ---------------------------

        self.rr_entity = rr_entity
        self.internal = {}
        self._rich_sort_params = dict(
            start_row=-1,
            count=-1,
            price_ranges=[],
            filter_attributes={}
        )
        self.base_url = 'http://recs.richrelevance.com/rrserver/'
        self.js_file_name = 'p13n_generated.js'
        self.placement_types = ''

    def rr_set_brand(self, brand):
        self.brand = self.rr_entity.fixName(brand)

    def set_session_id(self, a):
        self.session_id = a

    def set_user_id(self, a):
        self.user_id = a

    def add_item_id(self, idd, sku, place_to_add):
        place_to_add = _is_none(place_to_add)

        if sku is not None:
            idd = idd + "~" + sku

        place_to_add += '|' + self.rr_entity.fix_id(idd)

    def add_category_hint_id(self, a):
        if not self.category_hint_ids:
            self.category_hint_ids = ''

        self.category_hint_ids += '|' + self.rr_entity.fix_cat_id(a)

    def add_placement_type(self, placement_type):
        self.placement_types = _is_none(self.placement_types)
        self.placement_types += '|' + placement_type

    def add_search_term(self, search_term):
        self.search_terms = _is_none(self.search_terms)
        self.search_terms += '|' + search_term

    def set_api_key(self, api_key):
        self.api_key = api_key

    def set_registry_id(self, registry_id):
        self.registry_id = registry_id

    def block_item_id(self, idd):
        self.blocked_item_ids = _is_none(self.blocked_item_ids)
        self.blocked_item_ids += '|' + self.rr_entity.fix_id(idd)

    def init_from_params(self):
        if self.rr_entity.lc('r3_forceDisplay=true'):
            self.debug_mode = True
            self.display_mode_forced = 't'

        if self.rr_entity.lc('r3_forceDev=true'):
            self.debug_mode = True
            self.dev_mode_forced = 't'

        if self.rr_entity.lc('r3_rad=true'):
            self.debug_mode = True
            self.dev_mode_forced = 't'
            self.rad = True
            rad_level = self.rr_entity.pq('r3_radLevel')
            if rad_level is not '':
                self.rad_level = rad_level

        if self.rr_entity.lc('r3_useDummyData=true'):
            self.debug_mode = True
            self.dummy_data_used = 't'
            self.display_mode_forced = 't'

        temp_forced_treatment = self.rr_entity.pq('r3_forcedTreatment')
        if temp_forced_treatment:
            self.forced_treatment = temp_forced_treatment

        temp_forced_campaign = self.rr_entity.pq('r3_forcedCampaign')
        if temp_forced_campaign:
            self.forced_campaign = temp_forced_campaign

        temp_forced_campaign = self.rr_entity.pq('r3_fc')
        if temp_forced_campaign:
            self.forced_campaign = temp_forced_campaign

        temp_overridden_ip = self.rr_entity.pq('r3_ipOverride')
        if temp_overridden_ip:
            self.ip_override = temp_overridden_ip

        temp_forced_ftp = self.rr_entity.pq('r3_ftp')
        if temp_forced_ftp:
            self.forced_ftp = temp_forced_ftp

        temp_rap = self.rr_entity.pq('r3_responseDetails')
        if temp_rap:
            self.rap = temp_rap

        if self.rr_entity.lc('r3_debugMode=true'):
            self.debug_mode = True
        elif self.rr_entity.lc('r3_debugMode=false'):
            self.debug_mode = False

        if self.rr_entity.lc('rr_vg='):
            self.view_guid = self.rr_entity.pq('rr_vg')

        if self.view_guid is None and self.rr_entity.lc('vg='):
            self.view_guid = self.rr_entity.pq('vg')

        if self.rr_entity.lc('rm='):
            self.from_rich_mail = self.rr_entity.pq('rm')

        if self.rr_entity.lc('rr_u='):
            self.user_id = self.rr_entity.pq('rr_u')

        if self.rr_entity.lc('rr_pcam='):
            self.promo_campaign_id = self.rr_entity.pq('rr_pcam')

        if self.rr_entity.lc('rr_pcre='):
            self.promo_creative_id = self.rr_entity.pq('rr_pcre')

        if self.rr_entity.lc('rr_propt='):
            self.promo_placement_type = self.rr_entity.pq('rr_propt')

        if self.rr_entity.lc('rr_spoof='):
            self.spoof = self.rr_entity.pq('rr_spoof')

        if self.rr_entity.lc('rr_lpid='):
            self.landing_page_id = self.rr_entity.pq('rr_lpid')

    def add_core_params(self, script_src, path):
        script_src = self.base_url + path + '?' + urllib.urlencode({'a': self.api_key}) + script_src

        if self.placement_types:
            script_src += '&' + urllib.urlencode({'pt': self.placement_types})
            
        if self.user_id:
            script_src += '&' + urllib.urlencode({'u': self.user_id})

        if self.session_id:
            script_src += '&' + urllib.urlencode({'s': self.session_id})
        
        if self.view_guid:
            script_src += '&' + urllib.urlencode({'vg': self.view_guid})
        
        if self.segments:
            script_src += '&' + urllib.urlencode({'sgs': self.segments})
        
        if self.internal.get('channel'):
            script_src += '&' + urllib.urlencode({'channelId': self.internal.channel})
        
        return script_src
    
    def create_script(self, script_src, placements_empty, empty_placement_name):
        self.init_from_params()
        attribute_filters = []
        price_ranges = []
        price_range_index = 0
        
        if placements_empty:
            self.add_placement_type(empty_placement_name)
        
        script_src = self.add_core_params(script_src, self.js_file_name)

        if self.clickthru_server:
            script_src += '&' + urllib.urlencode({'cts': self.clickthru_server})

        if self.image_server:
            script_src += '&' + urllib.urlencode({'imgsrv': self.image_server})

        if self.json_enabled and self.json_enabled == 't':
            script_src += '&je=t'

        if self.landing_page_id is not None:
            script_src += '&lpid=' + self.landing_page_id

        if self.added_to_cart_item_ids:
            script_src += '&' + urllib.urlencode({'atcid': self.added_to_cart_item_ids})

        if self.internal.get('cart_value'):
            script_src += '&' + urllib.urlencode({'cv': self.internal['cart_value']})

        if self.forced_strategies:
            script_src += '&' + urllib.urlencode({'fs': self.forced_strategies})

        if self.listen_mode_forced and self.listen_mode_forced == 't':
            script_src += '&flm=t'

        if self.forced_treatment:
            script_src += '&' + urllib.urlencode({'ftr': self.forced_treatment})

        if self.forced_campaign:
            script_src += '&' + urllib.urlencode({'fcmpn': self.forced_campaign})

        if self.ip_override:
            script_src += '&' + urllib.urlencode({'ipor': self.ip_override})

        if self.forced_ftp:
            script_src += '&' + urllib.urlencode({'ftp': self.forced_ftp})

        if self.rap:
            script_src += '&' + urllib.urlencode({'rap': self.rap})

        if self.from_rich_mail:
            script_src += '&' + urllib.urlencode({'rm': self.from_rich_mail})

        if self.category_hint_ids:
            script_src += '&' + urllib.urlencode({'chi': self.category_hint_ids})

        if self.locale:
            script_src += '&' + urllib.urlencode({'flo': self.locale})

        if self.brand:
            script_src += '&' + urllib.urlencode({'fpb': self.brand})
        
        if self.uids is not None:
            script_src += '&' + urllib.urlencode({'uid': self.uids})
        
        if self.clearance_page is not None:
            script_src += '&' + urllib.urlencode({'clp': self.clearance_page})
        
        if self.filter_brands:
            script_src += '&' + urllib.urlencode({'filbr': self.filter_brands})
        
        if self.filter_brands_include:
            script_src += '&' + urllib.urlencode({'filbrinc': self.filter_brands_include})
        
        if self.filter_categories:
            script_src += '&' + urllib.urlencode({'filcat': self.filter_categories})
        
        if self.filter_categories_include:
            script_src += '&' + urllib.urlencode({'filcatinc': self.filter_categories_include})
        
        if self.filter_price_cents_min:
            script_src += '&' + urllib.urlencode({'filprcmin': self.filter_price_cents_min})
        
        if self.filter_price_cents_max:
            script_src += '&' + urllib.urlencode({'filprcmax': self.filter_price_cents_max})
        
        if self.filter_price_min:
            script_src += '&' + urllib.urlencode({'filprmin': self.filter_price_min})
        
        if self.filter_price_max:
            script_src += '&' + urllib.urlencode({'filprmax': self.filter_price_max})
        
        if self.filter_price_include:
            script_src += '&' + urllib.urlencode({'filprinc': self.filter_price_include})
        
        if self.clickthru_params:
            script_src += '&' + urllib.urlencode({'ctp': self.clickthru_params})
        
        if self.region_id:
            script_src += '&' + urllib.urlencode({'rid': self.region_id})
        
        if self.filters:
            script_src += '&' + urllib.urlencode({'if': self.filters})
        
        if self.refinements:
            script_src += '&' + urllib.urlencode({'rfm': self.refinements})
        
        if self.rad is not None:
            script_src += '&rad=t'
        
        if self.rad_level is not None:
            script_src += '&' + urllib.urlencode({'radl': self.rad_level})
        
        if self.promo_campaign_id is not None:
            script_src += '&' + urllib.urlencode({'pcam': self.promo_campaign_id})
        
        if self.promo_creative_id is not None:
            script_src += '&' + urllib.urlencode({'pcre': self.promo_creative_id})
        
        if self.promo_placement_type is not None:
            script_src += '&' + urllib.urlencode({'propt': self.promo_placement_type})
        
        if self.spoof is not None:
            script_src += '&spoof=' + self.spoof
        
        if self.internal.get('context') is not None:
            for prop in self.internal['context']:
                prop_value = self.internal['context'][prop]
                script_src += '&'
                
                if isinstance(prop_value, list):
                    script_src += urllib.urlencode({'prop': prop_value.join('|')})
                else:
                    script_src += urllib.urlencode({'prop': prop_value})
        
        if self.registry_id:
            script_src += '&' + urllib.urlencode({'rg': self.registry_id})
        
        if self.registry_type:
            script_src += '&' + urllib.urlencode({'rgt': self.registry_type})
        
        if self.search_terms is not None:
            script_src += '&' + urllib.urlencode({'st': self.search_terms})
        
        if self.json_callback:
            script_src += '&' + urllib.urlencode({'jcb': self.json_callback})
        
        if self.immediate_callback_forced:
            script_src += '&icf=t'
        
        if self.blocked_item_ids:
            script_src += '&' + urllib.urlencode({'bi': self.blocked_item_ids})
        
        if self.item_ids:
            script_src += '&' + urllib.urlencode({'p': self.item_ids})

        start_row = self._rich_sort_params.get('start_row', 0)
        if start_row > 0:
            script_src += '&' + urllib.urlencode({'rssr': start_row})

        count = self._rich_sort_params.get('count', 0)
        if count > 0:
            script_src += '&' + urllib.urlencode({'rsrc': count})

        price_ranges = self._rich_sort_params.get('price_ranges')
        if price_ranges:
            price_range_length = len(price_ranges)
            for price_range_index in range(price_range_length):
                price_ranges.append(
                    ';'.join(price_ranges[price_range_index])
                )
            
            script_src += '&' + urllib.urlencode({'rspr': '|'.join(price_ranges)})
            
        for attribute in self._rich_sort_params['filter_attributes']:
            attribute_filters.append(attribute + ':' + self._rich_sort_params['filter_attributes']['attribute'].join(';'))
        
        if len(attribute_filters) > 0:
            script_src += '&' + urllib.urlencode({'rsfoa': '|'.join(attribute_filters)})
        
        if self.debug_mode:
            if self.display_mode_forced and self.display_mode_forced == 't':
                script_src += '&fdm=t'
            
            if self.dev_mode_forced and self.dev_mode_forced == 't':
                script_src += '&dev=t'
            
            if self.dummy_data_used and self.dummy_data_used == 't':
                script_src += '&udd=t'
            
        script_src += '&l=1'
        return script_src
    

class R3Item(object):
    
    def __init__(self, rr_entity):

        init_params(self)

        self.rr_entity = rr_entity
        self.r3_entity = R3Common(self.rr_entity)
        self.block_item_id = self.r3_entity.block_item_id
        self.id = self.rr_entity.id

    def create_script(self, script_src):
        if self.top_level_genre:
            script_src += '&' + urllib.urlencode({'tg': self.top_level_genre})
        
        if self.categories:
            script_src += '&' + urllib.urlencode({'cs': self.categories})

        if self.category_ids:
            script_src += '&' + urllib.urlencode({'cis': self.category_ids})

        if self.id:
            script_src += '&' + urllib.urlencode({'p': self.id})

        if self.name:
            script_src += '&' + urllib.urlencode({'n': self.name})

        if self.description:
            script_src += '&' + urllib.urlencode({'d': self.description})

        if self.image_id:
            script_src += '&' + urllib.urlencode({'ii': self.image_id})

        if self.link_id:
            script_src += '&' + urllib.urlencode({'li': self.link_id})

        if self.release_date:
            script_src += '&' + urllib.urlencode({'rd': self.release_date})

        if self.dollars_and_cents:
            script_src += '&' + urllib.urlencode({'np': self.dollars_and_cents})

        if self.cents:
            script_src += '&' + urllib.urlencode({'npc': self.cents})

        if self.sale_dollars_and_cents:
            script_src += '&' + urllib.urlencode({'sp': self.sale_dollars_and_cents})

        if self.sale_cents:
            script_src += '&' + urllib.urlencode({'spc': self.sale_cents})

        if self.price:
            script_src += '&' + urllib.urlencode({'np': self.price})

        if self.sale_price:
            script_src += '&' + urllib.urlencode({'sp': self.sale_price})

        if self.end_date:
            script_src += '&' + urllib.urlencode({'ed': self.end_date})

        if self.rating:
            script_src += '&' + urllib.urlencode({'r': self.rating})

        if self.recommendable is not None:
            script_src += '&' + urllib.urlencode({'re': self.recommendable})

        if self.brand:
            script_src += '&' + urllib.urlencode({'b': self.brand})

        if self.attributes:
            script_src += '&' + urllib.urlencode({'at': self.attributes})

        if self.in_stock is not None:
            script_src += '&' + urllib.urlencode({'ins': self.in_stock})

        return script_src
    

class RR(object):

    def __init__(self, href, idd, response):
        self.r3_entity = R3Common(self)
        self.response = response
        self.href = href  # Product url
        self.id = idd  # Product ID
        self.charset = 'UTF-8'
        self.D = 'a5d5af7012d61fd1'
        self.T = '632d581ca7b9feb3'
        self.TD = '3e89ae564e77b361'
        self.TM = '|61e8c5b5ec8a3a00|421363196daa3779|73de560159c8c3b9|' \
                  'f0f1949cb6ae84eb|752e69416232e918|cc53d80ef0c355a7|5120f20de7f2261b|'

    def rrSetup(self):
        self.r3_entity.set_api_key("45c4b1787d30a004")

        # "S" parameter
        self.r3_entity.set_session_id('6b94d8fb-5f0f-42b2-a4ea-6d0d497c6427')

        # "U" parameter
        self.r3_entity.set_user_id('6b94d8fb-5f0f-42b2-a4ea-6d0d497c6427')

        chi = is_empty(
            re.findall(
                r'"primary_parent_id":\["(\d+)"\]',
                self.response.body_as_unicode()
            ), ''
        )
        if chi:
            self.r3_entity.add_category_hint_id(chi)

    def set_charset(self, c):
        self.charset = c

    def fix_name(self, name):
        result = name
        if r'&amp;' in name:
            result = name.replace('&amp;', "&")
        if r'&#039;' in name:
            result = name.replace('&#039;', "'")
        return result

    def fix_id(self, idd):
        result = idd.upper()
        return result

    def fix_cat_id(self, idd):
        return self.fix_id(self.fix_name(idd))

    def lc(self, n):
        if n.find('=') == -1:
            n += '='

        if n.find('?') == -1 and n.find('&') == -1:
            pidx = self.href.find('?' + n)
            if pidx == -1:
                pidx = self.href.find('&' + n)
            return pidx != -1
        else:
            return self.href.find()

    def pq(self, n):
        pidx = self.href.find("?" + n + '=')
        if pidx == -1:
            pidx = self.href.find("&" + n + '=')

        if pidx != -1:
            pidx = pidx + 1
            didx = self.href.find("&", pidx)

            if didx != -1:
                v = self.href.find(pidx + n.length + 1, didx)
            else:
                v = self.href.find(pidx + n.length + 1, self.href.length)
        else:
            v = ''

        return v

    def js(self):
        script_src = ''
        placements_empty = False
        empty_placement_name = 'item_page'

        self.rrSetup()

        RSobjs = self.response.css('section.recordSpotlight.richRelevance:not(.RRdone)')

        for key, obj in enumerate(RSobjs):
            self.r3_entity.add_placement_type("item_page.rr" + str(key+1))

            if not self.r3_entity.placement_types:
                placements_empty = True

        if R3Item:
            r3_pt = R3Item(self)
            script_src = r3_pt.create_script(script_src)

        script_src = self.r3_entity.create_script(script_src, placements_empty, empty_placement_name)
        return script_src
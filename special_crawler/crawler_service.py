#!/usr/bin/python
import os
import sys
import traceback

import boto
from boto.s3.key import Key

CWD = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.join(CWD, '..'))
sys.path.insert(1, os.path.join(CWD, '../product-ranking'))

from flask import Flask, jsonify, request
from extract_shopritedelivers_data import ShopritedeliversScraper
from extract_walmart_data import WalmartScraper
from extract_tesco_data import TescoScraper
from extract_amazon_data import AmazonScraper
from extract_pgestore_data import PGEStore
from extract_wayfair_data import WayfairScraper
from extract_bestbuy_data import BestBuyScraper
from extract_kmart_data import KMartScraper
from extract_ozon_data import OzonScraper
from extract_vitadepot_data import VitadepotScraper
from extract_argos_data import ArgosScraper
from extract_homedepot_data import HomeDepotScraper
from extract_statelinetack_data import StateLineTackScraper
from extract_impactgel_data import ImpactgelScraper
from extract_chicksaddlery_data import ChicksaddleryScraper
from extract_bhinneka_data import BhinnekaScraper
from extract_maplin_data import MaplinScraper
from extract_target_data import TargetScraper
from extract_chicago_data import ChicagoScraper
from extract_samsclub_data import SamsclubScraper
from extract_samsclub_shelf_data import SamsclubShelfScraper
from extract_babysecurity_data import BabysecurityScraper
from extract_staples_data import StaplesScraper
from extract_soap_data import SoapScraper
from extract_drugstore_data import DrugstoreScraper
from extract_staplesadvantage_data import StaplesAdvantageScraper
from extract_souq_data import SouqScraper
from extract_freshdirect_data import FreshDirectScraper
from extract_peapod_data import PeapodScraper
from extract_quill_data import QuillScraper
from extract_hersheys_data import HersheysScraper
from extract_george_data import GeorgeScraper
from extract_bloomingdales_data import BloomingdalesScraper
from extract_macys_data import MacysScraper
from extract_frys_data import FrysScraper
from extract_newegg_data import NeweggScraper
from extract_costco_data import CostcoScraper
from extract_proswimwear_data import ProswimwearScraper
from extract_ulta_data import UltaScraper
from extract_asda_data import AsdaScraper
from extract_kohls_data import KohlsScraper
from extract_jcpenney_data import JcpenneyScraper
from extract_wiggle_data import WiggleScraper
from extract_snapdeal_data import SnapdealScraper
from extract_walmartca_data import WalmartCAScraper
from extract_marksandspencer_data import MarksAndSpencerScraper
from extract_nextcouk_data import NextCoUKScraper
from extract_uniqlo_data import UniqloScraper
from extract_deliverywalmart_data import DeliveryWalmartScraper
from extract_flipkart_data import FlipkartScraper
from extract_pepperfry_data import PepperfryScraper
from extract_cvs_data import CVSScraper
from extract_walgreens_data import WalgreensScraper
from extract_hairshop24_data import HairShop24Scraper
from extract_hagelshop_data import HagelShopScraper
from extract_levi_data import LeviScraper
from extract_dockers_data import DockersScraper
from extract_houseoffraser_data import HouseoffraserScraper
from extract_schuh_data import SchuhScraper
from extract_boots_data import BootsScraper
from extract_newlook_data import NewlookScraper
from extract_clarkscouk_data import ClarksCoUkScraper
from extract_halfords_data import HalfordsScraper
from extract_homebase_data import HomebaseScraper
from extract_riverisland_data import RiverislandScraper
from extract_mothercare_data import MotherCareScraper
from extract_toysrus_data import ToysRusScraper
from extract_nike_data import NikeScraper
from extract_officedepot_data import OfficeDepotScraper
from extract_orientaltrading_data import OrientalTradingScraper
from extract_walmartmx_data import WalmartMXScraper
from extract_riteaid_data import RiteAidScraper
from extract_att_data import ATTScraper
from extract_verizonwireless_data import VerizonWirelessScraper
from extract_lowes_data import LowesScraper
from extract_petco_data import PetcoScraper
from extract_wag_data import WagScraper
from extract_chewy_data import ChewyScraper
from extract_petfooddirect_data import PetFoodDirectScraper
from extract_pet360_data import Pet360Scraper
from extract_petsmart_data import PetsmartScraper
from extract_walmartgrocery_data import WalmartGroceryScraper
from extract_samsung_data import SamsungScraper
from extract_autozone_data import AutozoneScraper
from extract_sears_data import SearsScraper
from extract_pepboys_data import PepboysScraper
from extract_jet_data import JetScraper
from extract_westmarine_data import WestmarineScraper
from extract_shoprite_data import ShopriteScraper
from extract_hayneedle_data import HayneedleScraper
from extract_ebags_data import EbagsScraper
from extract_ah_data import AhScraper
from extract_cheaperthandirt_data import CheaperthandirtScraper
from extract_rakuten_data import RakutenScraper
from extract_auchanfr_data import AuchanfrScraper
from extract_allmodern_data import AllmodernScraper
from extract_zulily_data import ZulilyScraper
from extract_anthropologie_data import AnthropologieScraper
from extract_currys_data import CurrysScraper
from extract_ikea_data import IkeaScraper
from extract_potterybarn_data import PotteryBarnScraper
from extract_boxed_data import BoxedScraper
from extract_crateandbarrel_data import CrateandbarrelScraper
from extract_johnlewis_data import JohnlewisScraper
from extract_walmartshelf_data import WalmartShelfScraper
from extract_cb2_data import Cb2Scraper
from extract_shoebuy_data import ShoeBuyScraper
from extract_westelm_data import WestElmScraper
from extract_landofnod_data import LandofNodScraper
from extract_chegg_data import CheggScraper
from extract_harristeeter_data import HarristeeterScraper
from extract_meijer_data import MeijerScraper
from extract_shopcoles_data import ShopColesScraper
from extract_overstock_data import OverstockScraper
from extract_kroger_data import KrogerScraper
from extract_woolworths_data import WoolworthsScraper
from extract_bigbasket_data import BigBasketScraper
from extract_gildanonline_data import GildanOnlineScraper
from extract_bedbathandbeyond_data import BedBathAndBeyondScraper
from extract_cymax_data import CymaxScraper
from extract_afo_data import AfoScraper
from extract_jumbo_data import JumboScraper
from extract_dollargeneral_data import DollarGeneralScraper
from extract_modcloth_data import ModClothScraper
from extract_sainsburys_data import SainsburysScraper
from extract_ocado_data import OcadoScraper
from extract_michaels_data import MichaelsScraper
from extract_jumbo_mobile_data import JumboMobileScraper
from extract_moosejaw_data import MoosejawScraper
from extract_waitrose_data import WaitroseScraper
from extract_build_data import BuildScraper
from extract_lowesca_data import LowesCAScraper
from extract_acehardware_data import AcehardwareScraper
from extract_treehouse_data import TreeHouseScraper
from extract_storegoogle_data import StoreGoogleScraper
from extract_barnesandnoble_data import BarnesandnobleScraper
from extract_morrisons_data import MorrisonsScraper
from extract_hsn_data import HsnScraper
from extract_bestbuy_canada_data import BestBuyCanadaScraper
from extract_dell_data import DellScraper
from extract_footlocker_data import FootlockerScraper
from extract_oldnavy_data import OldnavyScraper
from extract_adorama_data import AdoramaScraper
from extract_superdrug_data import SuperdrugScraper
from extract_123stores_data import StoresScraper
from extract_gap_data import GapScraper
from extract_microcenter_data import MicrocenterScraper
from extract_homedepotca_data import HomedepotcaScraper
from extract_accessoriesdell_data import AccessoriesDellScraper
from extract_truevalue_data import TruevalueScraper
from extract_groupon_data import GrouponScraper
from extract_poundland_data import PoundLandScraper
from extract_instacart_data import InstaCartScraper
from extract_priceline_data import PriceLineScraper
from extract_bhphotovideo_data import BhphotovideoScraper
from extract_chemistwarehouseau_data import ChemistwarehouseauScraper
from extract_icelandcouk_data import IcelandcoukScraper
from extract_menards_data import MenardsScraper
from extract_crutchfield_data import CrutchfieldScraper
from extract_grainger_data import GraingerScraper
from extract_gianteagle_data import GiantEagleScraper
from extract_bjs_data import BjsScraper
from extract_drizly_data import DrizlyScraper
from extract_publix_data import PublixScraper
from extract_dollartree_data import DollarTreeScraper
from extract_safeway_data import SafeWayScraper
from extract_heb_data import HebScraper
from extract_totalwine_data import TotalwineScraper
from extract_minibardelivery_data import MinibarDeliveryScraper
from extract_curbsideexpress_gianteagle_data import CurbSideExpressGiantEagleScraper
from extract_iteminfo_data import IteminfoScraper
from extract_usfoods_data import UsfoodsScraper
from extract_supplyworks_data import SupplyWorksScraper
from extract_carrefourit_data import CarrefourItScraper
from extract_carrefourfr_data import CarrefourFrScraper
from extract_rcwilley_data import RcwilleyScraper
from extract_nordstrom_data import NordStromScraper
from extract_osh_data import OshScraper
from extract_ronaca_data import RonacaScraper
from extract_abt_data import AbtScraper
from extract_google_express_data import GoogleExpressScraper
from extract_superama_data import SuperamaScraper
from extract_shopbfresh_data import ShopBfreshScraper
from extract_telusca_data import TelusCAScraper
from extract_costcobusinessdelivery_data import CostcobusinessdeliveryScraper
from extract_sephora_data import SephoraScraper
from extract_grocerygateway_data import GrocerygatewayScraper
from extract_surlatable_data import SurlatableScraper
from extract_williams_sonoma_data import WillamsSonomaScraper
from extract_plusnl_data import PlusnlScraper
from extract_coop_data import CoopScraper
from extract_bushfurniture2go_data import Bushfurniture2goScraper
from extract_buybuybaby_data import BuyBuyBabyScraper
from extract_loblaws_data import LoblawsScraper
from extract_joann_data import JoannScraper
from extract_sanalmarket_data import SanalmarketScraper
from extract_hepsiburada_data import HepsiburadaScraper
from extract_ebay_data import EbayScraper
from extract_carrefoursa_data import CarrefourSaScraper
from extract_vitacost_data import VitacostScraper
from extract_shoppersdrugmart_data import ShoppersdrugmartScraper
from extract_saveonfoods_data import SaveonfoodsScraper
from extract_fairprice_data import FairPriceScraper
from extract_redmart_data import RedmartScraper
from extract_alibaba_data import AlibabaScraper
from extract_lazadasg_data import LazadaSgScraper
from extract_nuevojumbo_data import NuevoJumboScraper

from urllib2 import HTTPError
import datetime
import logging
from logging import StreamHandler
import re
import json
from lxml import html
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time
import collections

app = Flask(__name__)

# dictionary containing supported sites as keys
# and their respective scrapers as values
SUPPORTED_SITES = {
                    "amazon" : AmazonScraper,
                    "bestbuy" : BestBuyScraper,
                    "homedepot" : HomeDepotScraper,
                    "statelinetack" : StateLineTackScraper,
                    "tesco" : TescoScraper,
                    "walmart" : WalmartScraper,
                    "argos": ArgosScraper,
                    "kmart" : KMartScraper,
                    "ozon" : OzonScraper,
                    "pgestore" : PGEStore,
                    "pgshop" : PGEStore,
                    "vitadepot": VitadepotScraper,
                    "wayfair" : WayfairScraper,
                    "impactgel" : ImpactgelScraper,
                    "chicksaddlery" : ChicksaddleryScraper,
                    "bhinneka" : BhinnekaScraper,
                    "maplin" : MaplinScraper,
                    "hersheysstore" : HersheysScraper,
                    "target" : TargetScraper,
                    "chicago" : ChicagoScraper,
                    "samsclub" : SamsclubScraper,
                    "samsclubshelf" : SamsclubShelfScraper,
                    "babysecurity" : BabysecurityScraper,
                    "staples" : StaplesScraper,
                    "soap" : SoapScraper,
                    "drugstore" : DrugstoreScraper,
                    "staplesadvantage" : StaplesAdvantageScraper,
                    "souq": SouqScraper,
                    "freshdirect" : FreshDirectScraper,
                    "quill" : QuillScraper,
                    "george" : GeorgeScraper,
                    "peapod" : PeapodScraper,
                    "bloomingdales" : BloomingdalesScraper,
                    "macys": MacysScraper,
                    "frys": FrysScraper,
                    "newegg": NeweggScraper,
                    "costco": CostcoScraper,
                    "proswimwear": ProswimwearScraper,
                    "ulta": UltaScraper,
                    "groceries": AsdaScraper,
                    "kohls": KohlsScraper,
                    "jcpenney": JcpenneyScraper,
                    "wiggle": WiggleScraper,
                    "snapdeal": SnapdealScraper,
                    "walmartca": WalmartCAScraper,
                    "marksandspencer": MarksAndSpencerScraper,
                    "nextcouk": NextCoUKScraper,
                    "uniqlo": UniqloScraper,
                    "deliverywalmart": DeliveryWalmartScraper,
                    "flipkart": FlipkartScraper,
                    "pepperfry": PepperfryScraper,
                    "cvs": CVSScraper,
                    "walgreens": WalgreensScraper,
                    "hairshop24": HairShop24Scraper,
                    "hagelshop": HagelShopScraper,
                    "levi": LeviScraper,
                    "dockers": DockersScraper,
                    "houseoffraser": HouseoffraserScraper,
                    "boots": BootsScraper,
                    "newlook": NewlookScraper,
                    "schuh": SchuhScraper,
                    "clarkscouk": ClarksCoUkScraper,
                    "halfords": HalfordsScraper,
                    "homebase": HomebaseScraper,
                    "riverisland": RiverislandScraper,
                    "mothercare": MotherCareScraper,
                    "toysrus": ToysRusScraper,
                    "nike": NikeScraper,
                    "officedepot": OfficeDepotScraper,
                    "orientaltrading": OrientalTradingScraper,
                    "walmartmx": WalmartMXScraper,
                    "riteaid": RiteAidScraper,
                    "att": ATTScraper,
                    "verizonwireless": VerizonWirelessScraper,
                    "lowes": LowesScraper,
                    "petco": PetcoScraper,
                    "wag": WagScraper,
                    "chewy" : ChewyScraper,
                    "petfooddirect": PetFoodDirectScraper,
                    "pet360" : Pet360Scraper,
                    "petsmart" : PetsmartScraper,
                    "walmartgrocery" : WalmartGroceryScraper,
                    "pepboys" : PepboysScraper,
                    "samsung" : SamsungScraper,
                    "shopritedelivers": ShopritedeliversScraper,
                    "autozone" : AutozoneScraper,
                    "sears" : SearsScraper,
                    "westmarine" : WestmarineScraper,
                    "jet" : JetScraper,
                    "shoprite" : ShopriteScraper,
                    "hayneedle" : HayneedleScraper,
                    "ebags" : EbagsScraper,
                    "auchan" : AuchanfrScraper,
                    "allmodern" : AllmodernScraper,
                    "ah" : AhScraper,
                    "zulily" : ZulilyScraper,
                    "cheaperthandirt" : CheaperthandirtScraper,
                    "rakuten" : RakutenScraper,
                    "anthropologie" : AnthropologieScraper,
                    "currys" : CurrysScraper,
                    "ikea" : IkeaScraper,
                    "potterybarn" : PotteryBarnScraper,
                    "boxed" : BoxedScraper,
                    'crateandbarrel': CrateandbarrelScraper,
                    "johnlewis" : JohnlewisScraper,
                    "shoebuy" : ShoeBuyScraper,
                    "walmartshelf" : WalmartShelfScraper,
                    "cb2" : Cb2Scraper,
                    "westelm" : WestElmScraper,
                    "landofnod" : LandofNodScraper,
                    "chegg" : CheggScraper,
                    "harristeeter": HarristeeterScraper,
                    "meijer": MeijerScraper,
                    "coles": ShopColesScraper,
                    "overstock": OverstockScraper,
                    "kroger": KrogerScraper,
                    "woolworths": WoolworthsScraper,
                    "bigbasket" : BigBasketScraper,
                    "cymax": CymaxScraper,
                    "gildanonline" : GildanOnlineScraper,
                    "bedbathandbeyond" : BedBathAndBeyondScraper,
                    "afo": AfoScraper,
                    "michaels": MichaelsScraper,
                    "jumbo": JumboScraper,
                    "dollargeneral": DollarGeneralScraper,
                    "ocado": OcadoScraper,
                    "modcloth": ModClothScraper,
                    "sainsburys": SainsburysScraper,
                    "build": BuildScraper,
                    "lowesca": LowesCAScraper,
                    "jumbo_mobile": JumboMobileScraper,
                    "waitrose": WaitroseScraper,
                    "acehardware": AcehardwareScraper,
                    "moosejaw": MoosejawScraper,
                    "treehouse": TreeHouseScraper,
                    "storegoogle": StoreGoogleScraper,
                    "barnesandnoble": BarnesandnobleScraper,
                    "morrison": MorrisonsScraper,
                    "hsn": HsnScraper,
                    "bestbuy_ca": BestBuyCanadaScraper,
                    "dell": DellScraper,
                    "footlocker": FootlockerScraper,
                    "oldnavy": OldnavyScraper,
                    'adorama': AdoramaScraper,
                    'superdrug': SuperdrugScraper,
                    "123stores": StoresScraper,
                    "gap": GapScraper,
                    "microcenter": MicrocenterScraper,
                    "homedepotca": HomedepotcaScraper,
                    "accessoriesdell": AccessoriesDellScraper,
                    "truevalue": TruevalueScraper,
                    "groupon": GrouponScraper,
                    "poundland": PoundLandScraper,
                    "priceline": PriceLineScraper,
                    "bhphotovideo": BhphotovideoScraper,
                    "instacart": InstaCartScraper,
                    "chemistwarehouse": ChemistwarehouseauScraper,
                    "icelandcouk": IcelandcoukScraper,
                    "crutchfield": CrutchfieldScraper,
                    "menards": MenardsScraper,
                    "grainger": GraingerScraper,
                    "publix": PublixScraper,
                    "dollartree": DollarTreeScraper,
                    "safeway": SafeWayScraper,
                    "gianteagle": GiantEagleScraper,
                    "bjs": BjsScraper,
                    "drizly": DrizlyScraper,
                    "heb": HebScraper,
                    "totalwine": TotalwineScraper,
                    "minibardelivery": MinibarDeliveryScraper,
                    "curbsideexpressgianteagle": CurbSideExpressGiantEagleScraper,
                    "iteminfo": IteminfoScraper,
                    "usfoods": UsfoodsScraper,
                    "supplyworks": SupplyWorksScraper,
                    "carrefourit": CarrefourItScraper,
                    "carrefourfr": CarrefourFrScraper,
                    "rcwilley": RcwilleyScraper,
                    "abt": AbtScraper,
                    "nordstrom": NordStromScraper,
                    "osh": OshScraper,
                    "ronaca": RonacaScraper,
                    "superama": SuperamaScraper,
                    "bfresh": ShopBfreshScraper,
                    "telus": TelusCAScraper,
                    "costcobusinessdelivery": CostcobusinessdeliveryScraper,
                    "google_express": GoogleExpressScraper,
                    "telus": TelusCAScraper,
                    "surlatable": SurlatableScraper,
                    "sephora": SephoraScraper,
                    "grocerygateway": GrocerygatewayScraper,
                    "williams-sonoma": WillamsSonomaScraper,
                    "plusnl": PlusnlScraper,
                    "coop": CoopScraper,
                    "bushfurniture2go": Bushfurniture2goScraper,
                    "buybuybaby": BuyBuyBabyScraper,
                    "loblaws": LoblawsScraper,
                    "joann": JoannScraper,
                    "sanalmarket": SanalmarketScraper,
                    "hepsiburada": HepsiburadaScraper,
                    "ebay": EbayScraper,
                    "carrefoursa": CarrefourSaScraper,
                    "vitacost": VitacostScraper,
                    "shoppersdrugmart": ShoppersdrugmartScraper,
                    "saveonfoods": SaveonfoodsScraper,
                    "fairprice": FairPriceScraper,
                    "redmart": RedmartScraper,
                    "alibaba": AlibabaScraper,
                    "lazada": LazadaSgScraper,
                    "nuevojumbo": NuevoJumboScraper,
                    }

# add logger
# using StreamHandler ensures that the log is sent to stderr to be picked up by uwsgi log
fh = StreamHandler()
fh.setLevel(logging.DEBUG)
app.logger.setLevel(logging.DEBUG)
app.logger.addHandler(fh)

class InvalidUsage(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

class GatewayError(Exception):
    status_code = 502

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

# validate input and raise exception with message for client if necessary
def check_input(url, is_valid_url, invalid_url_message=""):
    # TODO: complete these error messages with more details specific to the scraped site
    if not url:
        raise InvalidUsage("No input URL was provided.", 400)

    if not is_valid_url:
        try:
            error_message = "Invalid URL: " + str(url) + " " + str(invalid_url_message)
        except UnicodeEncodeError:
            error_message = "Invalid URL: " + url.encode("utf-8") + str(invalid_url_message)
        raise InvalidUsage(error_message, 400)

# infer domain from input URL
def extract_domain(url):
    if 'chicago.doortodoororganics.com' in url:
        # for chicago scraper
        # https://chicago.doortodoororganics.com/shop/products/rudis-white-hamburger-buns
        return 'chicago'
    if 'uae.souq.com' in url:
        # for souq scraper
        # http://uae.souq.com/ae-en/samsung-galaxy-s3-mini-i8190-8gb-3g-+-wifi-white-4750807/i/
        return 'souq'
    if 'direct.asda.com' in url:
        return 'george'
    if 'groceries.asda.com' in url:
        return 'groceries'
    if re.match(WalmartShelfScraper.URL_FORMAT_REGEX, url):
        return 'walmartshelf'
    if 'walmart.ca' in url:
        return 'walmartca'
    if 'walmart.com.mx' in url:
        return 'walmartmx'
    if 'next.co.uk' in url:
        return 'nextcouk'
    if 'delivery.walmart' in url:
        return "deliverywalmart"
    if 'hair-shop24' in url:
        return "hairshop24"
    if 'hagel-shop' in url:
        return "hagelshop"
    if "www.clarks.co.uk" in url:
        return "clarkscouk"
    if "store.nike.com" in url:
        return "nike"
    if 'grocery.walmart.com' in url:
        return 'walmartgrocery'
    if 'primenow.amazon' in url:
        return 'amazon'
    if 'shoes.com' in url:
        return 'shoebuy'
    if 'lowes.ca' in url:
        return 'lowesca'
    if 'mobile.jumbo.com' in url:
        return 'jumbo_mobile'
    if 'tree.house' in url:
        return 'treehouse'
    if 'store.google.com' in url:
        return 'storegoogle'
    if 'groceries.morrisons.com' in url:
        return 'morrison'
    if 'bestbuy.ca' in url:
        return 'bestbuy_ca'
    if 'oldnavy.gap.com' in url:
        return 'oldnavy'
    if 'homedepot.ca' in url:
        return 'homedepotca'
    if 'accessories.dell' in url:
        return 'accessoriesdell'
    if 'iceland.co.uk' in url:
        return 'icelandcouk'
    if 'shop.albertsons' in url:
        return 'safeway'
    if 'shop.vons' in url:
        return 'safeway'
    if 'curbsideexpress.gianteagle.com' in url:
        return 'curbsideexpressgianteagle'
    if 'carrefour.it' in url:
        return 'carrefourit'
    if 'rueducommerce.fr' in url:
        return 'carrefourfr'
    if 'rona.ca' in url:
        return 'ronaca'
    if 'express.google.com' in url:
        return 'google_express'
    if SamsclubScraper._is_shelf_url(url):
        return 'samsclubshelf'
    if 'plus.nl' in url:
        return 'plusnl'
    if 'cgi.ebay.com' in url:
        return 'ebay'
    if 'nuevo.jumbo.cl' in url:
        return 'nuevojumbo'

    m = re.match("^https?://((m|www|shop|www1|intl|www3)\.)?([^/\.]+)\..*$", url)
    if m:
        return m.group(3).lower()
    # TODO: return error message about bad URL if it does not match the regex



# validate request mandatory arguments
def validate_args(arguments):
    # normalize all arguments to str
    argument_keys = map(lambda s: str(s), arguments.keys())

    mandatory_keys = ['url']

    # If missing any of the needed arguments, throw exception
    for argument in mandatory_keys:
        if argument not in argument_keys:
            raise InvalidUsage("Invalid usage: missing GET parameter: " + argument)

    # Validate site
    # If no "site" argument was provided, infer it from the URL
    if 'site' in arguments:
        site_argument = arguments['site'][0]
    else:
        site_argument = extract_domain(arguments['url'][0])

        # If site could not be extracted the URL was invalid
        if not site_argument:
            raise InvalidUsage("Invalid input URL: " + arguments['url'][0] + ". Domain could not be extracted")

        # Add the extracted site to the arguments list (to be used in get_data)
        arguments['site'] = [site_argument]

    if site_argument not in SUPPORTED_SITES.keys():
        raise InvalidUsage("Unsupported site: " + site_argument)

# validate request mandatory arguments
def validate_google_search_args(arguments):
    # normalize all arguments to str
    argument_keys = map(lambda s: str(s), arguments.keys())

    mandatory_keys = ['query']

    # If missing any of the needed arguments, throw exception
    for argument in mandatory_keys:
        if argument not in argument_keys:
            raise InvalidUsage("Invalid usage: missing GET parameter: " + argument)

    if 'sellers_search_only' in arguments:
        if arguments["sellers_search_only"][0].lower() not in ["true", "false"]:
            raise InvalidUsage("Invalid usage: invalid TYPE parameter: sellers_search_only")

# validate request "data" parameters
def validate_data_params(arguments, ALL_DATA_TYPES):
    # Validate data

    if 'data' in arguments:
        # TODO: do the arguments need to be flattened?
        data_argument_values = map(lambda s: str(s), arguments['data'])
        data_permitted_values = map(lambda s: str(s), ALL_DATA_TYPES.keys())

        # if there are other keys besides "data" or other values outside of the predefined data types (DATA_TYPES), return invalid usage
        if set(data_argument_values).difference(set(data_permitted_values)):
            # TODO:
            #      improve formatting of this message
            raise InvalidUsage("Invalid usage: Request arguments must be of the form '?url=<url>?site=<site>?data=<data_1>&data=<data_2>&data=<data_2>...,\n \
                with the <data_i> values among the following keywords: \n" + str(data_permitted_values))


# sort dict keys like natural view
# ex:
#   {"b2": 1, "b1": 1, "b11": 1, "b21": 1, "b12": 1} => {"b1": 1, "b2": 1, "b11": 1, "b12": 1, "b21": 1}
#
def natural_sort(d):

    def atoi(text):
        return int(text) if text.isdigit() else text

    def natural_keys(text):
        return [atoi(c) for c in re.split('(\d+)', text)]
    try:
        if not isinstance(d, (dict)):
            return d, True

        is_sorted = True
        keys = d.keys()
        keys.sort(key=natural_keys)

        dict_val = []
        for key in keys:
            sd, status = natural_sort(d[key])
            dict_val += [(key, sd)]
            if not status:
                is_sorted = False
                break

        return collections.OrderedDict(dict_val), is_sorted
    except:
        return d, False


# general resource for getting data.
# needs "url" and "site" parameters. optional parameter: "data"
# can be used without "data" parameter, in which case it will return all data
# or with arguments like "data=<data_type1>&data=<data_type2>..." in which case it will return the specified data
# the <data_type> values must be among the keys of DATA_TYPES imported dictionary
@app.route('/get_data', methods=['GET'])
def get_data():
    # this is used to convert an ImmutableMultiDictionary into a regular dictionary. will be left with only one "data" key
    request_arguments = dict(request.args)

    # validate request parameters
    validate_args(request_arguments)

    url = request_arguments.pop('url')[0]
    site = request_arguments.pop('site')[0]

    additional_requests = request_arguments.pop('additional_requests')[0] \
        if request_arguments.get('additional_requests') else None

    get_image_dimensions = request_arguments.pop('get_image_dimensions')[0] \
        if request_arguments.get('get_image_dimensions') else None

    zip_code = request_arguments.pop('zip_code')[0] \
        if request_arguments.get('zip_code') else None

    crawl_date = request_arguments.pop('crawl_date')[0] \
        if request_arguments.get('crawl_date') else None

    # add all other requests arguments to url
    for arg, argval in request_arguments.iteritems():
        url += '&' + arg
        if argval[0]:
            url += '=' + argval[0]

    proxy_config = {}

    amazon_bucket_name = 'ch-settings'
    key_file = 'proxy_settings_master.cfg'

    try:
        S3_CONN = boto.connect_s3(is_secure=False)
        S3_BUCKET = S3_CONN.get_bucket(amazon_bucket_name,
                                       validate=False)
        k = Key(S3_BUCKET)
        k.key = key_file
        proxy_config = json.loads(k.get_contents_as_string())

    except:
        print traceback.format_exc()

    # create scraper class for requested site
    site_scraper = SUPPORTED_SITES[site](
        url = url,
        additional_requests = additional_requests,
        get_image_dimensions = get_image_dimensions,
        proxy_config = proxy_config.get(site) or proxy_config.get('default'),
        zip_code=zip_code,
        crawl_date=crawl_date
    )

    # validate parameter values
    # url
    is_valid_url = site_scraper.check_url_format()
    if hasattr(site_scraper, "INVALID_URL_MESSAGE"):
        check_input(url, is_valid_url, site_scraper.INVALID_URL_MESSAGE)
    else:
        check_input(url, is_valid_url)

    # data
    validate_data_params(request_arguments, site_scraper.ALL_DATA_TYPES)

    is_ret_sorted = False
    if 'data' not in request_arguments:
        # return all data if there are no "data" parameters
        try:
            ret_uf = site_scraper.product_info()
            # make natural sort for amazon data
            ret, is_ret_sorted = natural_sort(ret_uf)
        except HTTPError as ex:
            raise GatewayError("Error communicating with site crawled.")
    else:
        # return only requested data
        try:
            ret_uf = site_scraper.product_info(request_arguments['data'])
            # make natural sort for amazon data
            ret, is_ret_sorted = natural_sort(ret_uf)
        except HTTPError:
            raise GatewayError("Error communicating with site crawled.")

    ret['scraper_type'] = site

    if is_ret_sorted:
        # Tf site is "Amazon", this API output a json as natural_sort.
        return app.response_class(json.dumps(ret, indent=2), mimetype='application/json')
    else:
        # Else this API use default output ( use jsonify sort )
        return jsonify(ret)



@app.route('/google_search', methods=['GET'])
def google_search():

    # this is used to convert an ImmutableMultiDictionary into a regular dictionary. will be left with only one "data" key
    request_arguments = dict(request.args)

    # validate request parameters
    validate_google_search_args(request_arguments)
    sellers_search_only = True if request_arguments.get("sellers_search_only", [""])[0].lower() == "true" else False
    query = request_arguments['query'][0]
    results = {}

    driver = webdriver.PhantomJS()
    driver.set_window_size(1440, 900)

    try:
        if sellers_search_only:
            driver.get("https://www.google.com/shopping?hl=en")
        else:
            #means broad search
            driver.get("https://www.google.com/")

        input_search_text = None

        if sellers_search_only:
            input_search_text = driver.find_element_by_xpath("//input[@title='Search']")
        else:
            input_search_text = driver.find_element_by_xpath("//input[@title='Google Search']")

        input_search_text.clear()
        input_search_text.send_keys('"' + query + '"')
        input_search_text.send_keys(Keys.ENTER)
        time.sleep(3)

        google_search_results_page_raw_text = driver.page_source
        google_search_results_page_html_tree = html.fromstring(google_search_results_page_raw_text)

        if google_search_results_page_html_tree.xpath("//form[@action='CaptchaRedirect']"):
            raise Exception('Google blocks search requests and claim to input captcha.')

        if google_search_results_page_html_tree.xpath("//title") and \
                        "Error 400 (Bad Request)" in google_search_results_page_html_tree.xpath("//title")[0].text_content():
            raise Exception('Error 400 (Bad Request)')

        if sellers_search_only:
            seller_block = None

            for left_block in google_search_results_page_html_tree.xpath("//ul[@class='sr__group']"):
                if left_block.xpath("./li[@class='sr__title sr__item']/text()")[0].strip().lower() == "seller":
                    seller_block = left_block
                    break

            seller_name_list = None

            if seller_block:
                seller_name_list = seller_block.xpath(".//li[@class='sr__item']//a/text()")
                seller_name_list = [seller for seller in seller_name_list if seller.lower() != "walmart"]

            if not seller_name_list:
                results["success"] = 1
                results["message"] = "Unique content."
            else:
                results["success"] = 1
                results["message"] = "Found duplicate content from other sellers: ." + ", ".join(seller_name_list)
        else:
            duplicate_content_links = google_search_results_page_html_tree.xpath("//div[@id='search']//cite/text()")

            if duplicate_content_links:
                duplicate_content_links = [url for url in duplicate_content_links if "walmart.com" not in url.lower()]

            if not duplicate_content_links:
                results["success"] = 1
                results["message"] = "Unique content."
            else:
                results["success"] = 1
                results["message"] = "Found duplicate content from other links."

    except Exception, e:
        print e
        results["success"] = 0
        results["message"] = str(e)

    driver.close()
    driver.quit()

    return jsonify(results)

@app.errorhandler(InvalidUsage)
def handle_invalid_usage(error):
    #TODO: not leave this as json output? error format should be consistent
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.errorhandler(GatewayError)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.errorhandler(404)
def handle_not_found(error):
    response = jsonify({"error" : "Not found"})
    response.status_code = 404
    return response

@app.errorhandler(500)
def handle_internal_error(error):
    response = jsonify({"error" : "Internal server error"})
    response.status_code = 500
    return response

# post request logger
@app.after_request
def post_request_logging(response):
    app.logger.info(json.dumps({
        "date" : datetime.datetime.today().ctime(),
        "remote_addr" : request.remote_addr,
        "request_method" : request.method,
        "request_url" : request.url,
        "response_status_code" : str(response.status_code),
        "request_headers" : ', '.join([': '.join(x) for x in request.headers])
        })
    )

    return response

if __name__ == '__main__':

    app.run('0.0.0.0', port=80, threaded=True)

"""insights_api URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin
from rest_framework import routers

from api_control.views import ProductListViewSet, SitesViewSet, \
    SearchTermsViewSet, DateViewSet, BrandsViewSet, \
    SearchTermsGroupsViewSet, PriceDataViewSet, RankingDataViewSet, \
    OutOfStockDataViewSet, BuyBoxDataViewSet, ReviewDataViewSet

# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'product_lists', ProductListViewSet, base_name='productlists')
router.register(r'search_terms', SearchTermsViewSet, base_name='searchterms')
router.register(r'search_terms_groups', SearchTermsGroupsViewSet, base_name='searchtermgroups')
router.register(r'sites', SitesViewSet, base_name='sites')
router.register(r'brands', BrandsViewSet, base_name='brands')
router.register(r'dates', DateViewSet, base_name='dates')
router.register(r'price_data', PriceDataViewSet, base_name='pricesdata')
router.register(r'ranking_data', RankingDataViewSet, base_name='rakingsdata')
router.register(
    r'out_of_stock_data', OutOfStockDataViewSet, base_name='oufofstocksdata')
router.register(r'buy_box_data', BuyBoxDataViewSet, base_name='buyboxesdata')
router.register(r'reviews_data', ReviewDataViewSet, base_name='reviews_data')


urlpatterns = [
    url(r'^restapi/admin/', admin.site.urls),
    url(r'^restapi/', include(router.urls)),
]

from django.conf.urls import url, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns
from image_duplication.views import (
    CompareTwoImageViewSet,
    ClassifyImagesBySimilarity,
    FindSimilarityInImageList,
    CompareTwoImageLists
)
from walmart_developer_accounts.views import WalmartAccountViewSet
from walmart_api.views import (
    InvokeWalmartApiViewSet,
    ItemsUpdateWithXmlFileByWalmartApiViewSet,
    ItemsUpdateWithXmlTextByWalmartApiViewSet,
    CheckFeedStatusByWalmartApiViewSet,
    ValidateWalmartProductXmlTextViewSet,
    ValidateWalmartProductXmlFileViewSet,
    FeedIDRedirectView,
    DetectDuplicateContentByMechanizeViewset,
    DetectDuplicateContentFromCsvFilesByMechanizeViewset,
    FeedStatusAjaxView,
    CheckItemStatusByProductIDViewSet,
    XMLFileRedirect,
    ToolIDViewSet,
    ListItemsWithErrorViewSet,
    RichMediaViewSet,
    DetailedViewViewSet,
)
from mocked_walmart_api.views import (
    MockedCheckFeedStatusByWalmartApiViewSet,
    MockedItemsUpdateWithXmlFileByWalmartApiViewSet,
    MockedFeedStatusAjaxView
)
from statistics.views import StatsView
from nutrition_info_images.views import ClassifyTextImagesByNutritionInfoViewSet
from settings import IS_PRODUCTION


CheckFeedStatusView = CheckFeedStatusByWalmartApiViewSet
ItemsUpdateView = ItemsUpdateWithXmlFileByWalmartApiViewSet
FeedStatusView = FeedStatusAjaxView
if not IS_PRODUCTION:
    CheckFeedStatusView = MockedCheckFeedStatusByWalmartApiViewSet
    ItemsUpdateView = MockedItemsUpdateWithXmlFileByWalmartApiViewSet
    FeedStatusView = MockedFeedStatusAjaxView
admin.autodiscover()

# # API endpoints
urlpatterns = format_suffix_patterns(
    [
        url(
            r'^items_update_with_xml_file_by_walmart_api/$',
            ItemsUpdateView.as_view({'get': 'list', 'post': 'create'}),
            name='items_update_with_xml_file_by_walmart_api'
        ),
        url(
            r'^check_feed_status_by_walmart_api/$',
            CheckFeedStatusView.as_view({'get': 'list', 'post': 'create'}),
            name='check_feed_status_by_walmart_api'
        ),
        url(
            r'^check_item_status_by_product_id/$',
            CheckItemStatusByProductIDViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='check_item_status_by_product_id'
        ),
        url(
            r'^validate_walmart_product_xml_file/$',
            ValidateWalmartProductXmlFileViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='validate_walmart_product_xml_file'
        ),
        url(
            r'^tool_id/$', ToolIDViewSet.as_view({'get': 'list', 'post': 'create'}), name='tool_id'
        ),
        url(
            r'^list_items_with_errors/$', ListItemsWithErrorViewSet.as_view({'get': 'list'}), name='items_with_errors'
        ),
        url(
            r'^rich_media/$',
            RichMediaViewSet.as_view({'get': 'list', 'post': 'create'}),
            name='rich_media'
        ),
        url(
            r'^detailed_view/$', DetailedViewViewSet.as_view({'get': 'list'}), name='detailed_view'
        ),
    ]
)

urlpatterns += [
    url(r'^feed-redirect/(?P<feed_id>[A-Za-z0-9\-@_]+)', FeedIDRedirectView.as_view(), name='feed_redirect'),
    url(r'^xml-file-redirect/(?P<feed_id>[A-Za-z0-9\-@_]+)', XMLFileRedirect.as_view(), name='xml_file_redirect'),
    url(r'^feed-status-ajax/(?P<feed_id>[A-Za-z0-9\-@_]+)', FeedStatusView.as_view(), name='feed_status_ajax'),
    # url(r'^stat-counter-ajax/', GetStatsAjax.as_view(), name='get_stats_ajax'),
    url(r'^stats/$', StatsView.as_view(), name='stats_view'),
    url(r'^ckeditor/', include('ckeditor_uploader.urls')),
]

if 'fcgi' in settings.INSTALLED_APPS:
    urlpatterns += [
        url(r'^fcgi/', include('fcgi.urls')),
    ]

router = routers.SimpleRouter()
router.register(r'comparetwoimages', CompareTwoImageViewSet, 'comparetwoimages')
router.register(r'classifyimagesbysimilarity', ClassifyImagesBySimilarity, 'classifyimagesbysimilarity')
router.register(r'findsimilarityinimagelist', FindSimilarityInImageList, 'findsimilarityinimagelist')
router.register(r'comparetwoimagelists', CompareTwoImageLists, 'comparetwoimagelists')
router.register(r'walmartaccounts', WalmartAccountViewSet, 'walmartaccounts')
router.register(
    r'classifytextimagesbynutritioninfo', ClassifyTextImagesByNutritionInfoViewSet, 'classifytextimagesbynutritioninfo'
)

if IS_PRODUCTION:
    router.register(r'invokewalmartapi', InvokeWalmartApiViewSet, 'invokewalmartapi')
    router.register(
        r'items_update_with_xml_text_by_walmart_api',
        ItemsUpdateWithXmlTextByWalmartApiViewSet,
        'items_update_with_xml_text_by_walmart_api'
    )
# router.register(r'check_feed_status_by_walmart_api',
#                CheckFeedStatusByWalmartApiViewSet,
#                'check_feed_status_by_walmart_api')
router.register(
    r'validate_walmart_product_xml_text', ValidateWalmartProductXmlTextViewSet, 'validate_walmart_product_xml_text'
)
router.register(r'detect_duplicate_content', DetectDuplicateContentByMechanizeViewset, 'detect_duplicate_content')
router.register(
    r'detect_duplicate_content_by_mechanize',
    DetectDuplicateContentByMechanizeViewset,
    'detect_duplicate_content_by_mechanize'
)
router.register(
    r'detect_duplicate_content_from_csv_file_by_mechanize',
    DetectDuplicateContentFromCsvFilesByMechanizeViewset,
    'detect_duplicate_content_from_csv_file_by_mechanize'
)
# router.register(
#     r'validate_walmart_product_xml_file', ValidateWalmartProductXmlFileViewSet, 'validate_walmart_product_xml_file'
# )

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns += [
    url(r'^', include(router.urls)),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^accounts/', include('accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

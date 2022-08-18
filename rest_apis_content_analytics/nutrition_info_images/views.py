from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from nutrition_info_images.serializers import ImageUrlSerializer
from classify_text_images import classifier_predict_one, load_classifier, predict_textimage_type
from rest_apis_content_analytics.image_duplication.views import parse_data

image_classifier = load_classifier()


# Create your views here.
def get_image_type(image_url):
    '''Predicts if image is a text image or not (nutrition/drug/supplement)
    and which type (nutrition/drug/supplement facts)
    Returns 1 of 5 values:
    nutrition_facts, drug_facts, supplement_facts, unknown (if text image but type unknown)
    and None (if not text image at all)
    '''

    # not a text image at all
    if classifier_predict_one(image_url, image_classifier) == 0:
        return None

    image_type = predict_textimage_type(image_url)
    if not image_type:
        return "unknown"

    return image_type


class ClassifyTextImagesByNutritionInfoViewSet(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = ImageUrlSerializer

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    def create(self, request):
        serializer = self.serializer_class(data=parse_data(request.data))

        if serializer.is_valid():
            try:
                urls = serializer.data["urls"]
                results = {}

                results={image : get_image_type(image) for image in urls}

                return Response(results)
            except:
                pass

        return Response({'data': 'NO OK'})

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})

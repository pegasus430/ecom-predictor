import os
import re
import cv2
import urllib
import cStringIO
import copy
import traceback
import socket

from PIL import Image
import numpy as np
from StringIO import StringIO
from rest_framework import viewsets
from rest_framework.parsers import JSONParser
from rest_apis_content_analytics.image_duplication.serializers import ImageUrlSerializer, CompareTwoImageListsSerializer
from rest_apis_content_analytics.image_duplication.compare_images import url_to_image, compare_two_images_a, compare_two_images_b, compare_two_images_c
from rest_framework.response import Response
import linecache
import sys


def parse_data(data):
    # If this key exists, it means that a raw JSON was passed via the Browsable API
    # TODO: it's a quick&dirty workaround, it should not work this way!
    if '_content' in data:
        stream = StringIO(data['_content'])
        return JSONParser().parse(stream)
    return data


def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print 'EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj)


class CompareTwoImageViewSet(viewsets.ViewSet):
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

                if not urls:
                    urls = request.data["urls"].split(" ")

                images_a  = []
                images_b = []
                images_c = []

                for url in urls:
                    path, ext = os.path.splitext(url)
                    path += ".jpg"

                    is_local = os.path.isfile(url)

                    if bool(re.findall("^[a-zA-Z]+://", url)):
                        resp = urllib.urlopen(url).read()
                        image = np.asarray(bytearray(resp), dtype="uint8")
                        images_a.append(cv2.imdecode(image, cv2.IMREAD_COLOR))
                        images_b.append(Image.open(cStringIO.StringIO(resp)))
                        images_c.append(Image.open(cStringIO.StringIO(resp)))

                    if ext not in (".jpg", ".jpeg", ".png"):
                        if is_local:
                            Image.open(path).convert('RGB').save(path)
                            image = cv2.imread(path)
                        else:
                            im = Image.open(StringIO(urllib.urlopen(url).read()))
                            file_mem = StringIO()
                            im.convert('RGB').save(file_mem, format="PNG")
                            file_mem.seek(0)
                            img_array = np.asarray(bytearray(file_mem.read()), dtype=np.uint8)
                            image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                            file_mem.close()

                        images_a.append(image)

                similarity_rate = float(compare_two_images_b(images_b[0], images_b[1])) * float(compare_two_images_c(images_c[0], images_c[1]))

                if similarity_rate >= 0.5:
                    return Response({'Are two images similar?': "Yes"})
                else:
                    return Response({'Are two images similar?': "No"})
            except:
                var = traceback.format_exc()

        return Response({'data': var})

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class ClassifyImagesBySimilarity(viewsets.ViewSet):
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
                socket.setdefaulttimeout(60)
                urls = serializer.data["urls"]

                if not urls:
                    urls = request.data["urls"].split(" ")

                images = {}

                for url in urls:
                    if bool(re.findall("^[a-zA-Z]+://", url)):
                        try:
                            resp = urllib.urlopen(url).read()
                            images[url] = Image.open(cStringIO.StringIO(resp))
                        except:
                            pass

                rest_images = copy.copy(images)
                results = []

                for url1 in images:
                    if not rest_images:
                        break

                    if url1 not in rest_images:
                        continue

                    del rest_images[url1]
                    group_image_indexes = [url1]

                    processed_images = []

                    for url2 in rest_images:

                        similarity_rate = float(compare_two_images_c(images[url1], rest_images[url2])) * float(compare_two_images_b(images[url1], rest_images[url2]))

                        if similarity_rate >= 0.5:
                            processed_images.append(url2)
                            group_image_indexes.append(url2)

                    for url in processed_images:
                        del rest_images[url]

                    results.append(group_image_indexes)

                return Response(results)
            except Exception, e:
                PrintException()
                print e

        return Response({'data': 'NO OK'})

    def update(self, request, pk=None):
        pass

    def partial_update(self, request, pk=None):
        return Response({'data': 'OK'})

    def destroy(self, request, pk=None):
        return Response({'data': 'OK'})


class FindSimilarityInImageList(viewsets.ViewSet):
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
                socket.setdefaulttimeout(60)
                urls = serializer.data["urls"]

                images = {}

                for url in urls:
                    if bool(re.findall("^[a-zA-Z]+://", url)):
                        try:
                            resp = urllib.urlopen(url).read()
                            image = Image.open(cStringIO.StringIO(resp))

                            if image.mode == 'RGBA':
                                background = Image.new('RGBA', image.size, (255, 255, 255))
                                image = Image.alpha_composite(background, image)

                            images[url] = image
                        except:
                            pass

                rest_images = copy.copy(images)
                results = {}

                url1 = urls[0]

                del rest_images[url1]
                group_image_indexes = []

                processed_images = []

                for url2 in rest_images:

                    similarity_rate = float(compare_two_images_c(images[url1], rest_images[url2])) * float(compare_two_images_b(images[url1], rest_images[url2]))

                    if similarity_rate >= 0.7:
                        processed_images.append(url2)
                        group_image_indexes.append(url2)

                if group_image_indexes:
                    results["similar_images"] = group_image_indexes
                    results["result"] = "Yes"
                else:
                    results["similar_images"] = None
                    results["result"] = "No"

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


class CompareTwoImageLists(viewsets.ViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    serializer_class = CompareTwoImageListsSerializer

    def list(self, request):
        return Response({'data': 'OK'})

    def retrieve(self, request, pk=None):
        return Response({'data': 'OK'})

    def create(self, request):
        serializer = self.serializer_class(data=parse_data(request.data))

        if serializer.is_valid():
            try:
                urls1 = serializer.data["urls1"]
                urls2 = serializer.data["urls2"]

                images_2 = []

                for url2 in urls2:
                    resp = urllib.urlopen(url2).read()
                    images_2.append(Image.open(cStringIO.StringIO(resp)))

                results = {}

                for url1 in urls1:
                    resp = urllib.urlopen(url1).read()
                    image1 = Image.open(cStringIO.StringIO(resp))

                    images = dict(zip(urls2, images_2))

                    rest_images = copy.copy(images)

                    group_image_indexes = []

                    processed_images = []

                    for url2 in rest_images:

                        similarity_rate = float(compare_two_images_c(image1, rest_images[url2])) * float(compare_two_images_b(image1, rest_images[url2]))

                        if similarity_rate >= 0.8:
                            processed_images.append(url2)
                            group_image_indexes.append(url2)

                    if group_image_indexes:
                        results[url1] = group_image_indexes
                    else:
                        results[url1] = None

                if results:
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

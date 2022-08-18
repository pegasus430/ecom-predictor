from six import StringIO
from six.moves import urllib

from PIL import Image
from pytesseract import image_to_string

letters = []
angles = [10, -15, 20, -15, 10, -10]

class AmazonCaptchaSolver:

    def __init__(self):
        self.config = '-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ -c oem=1 -c psm=13'
        self.offset = 0
        self.most_black = 40

    def solve_captcha(self, url):
        _image = self.get_image_from_url(url)
        width, height = _image.size
        image = Image.new('L', (width, height), 'white')
        image.paste(_image.crop((10, 0, width, height)))
        image.paste(_image.crop((0, 0, 10, height)), (width-10, 0))
        for most_black in range(1, self.most_black+1)[::-1]:
            borders = self.get_borders(image, most_black)
            if len(borders) == 7:
                break
        letters = self.devide_letters(image, borders)
        result = self.draw_image_from_letters(letters)
        answer = image_to_string(
            result,
            config=self.config
        ).strip().replace(' ', '')
        _image.close()
        image.close()
        result.close()
        return answer

    def get_borders(self, image, most_black):
        _borders = []
        borders = [self.offset]

        width, height = image.size
        for w in range(width):
            black_pixels = 0
            for h in range(height):
                pixel = image.getpixel((w, h))
                if pixel < most_black:
                    black_pixels += 1
            if black_pixels >= 2:
                _borders.append(w)

        _borders = sorted(list(set(range(_borders[0], _borders[-1]+1)) - set(_borders)))
        for i, num in enumerate(_borders):
            if num > borders[-1]+15:
                borders.append(num+1)
        borders.append(width)
        return borders

    @staticmethod
    def devide_letters(image, borders):
        letters = []
        for n in range(0, len(borders) - 1):
            _image = Image.new('RGBA', (borders[n + 1] - borders[n], 50))
            for i, v in enumerate(range(borders[n], borders[n + 1])):
                for h in range(50):
                    _image.putpixel((i, h), (image.getpixel((v, h)),) * 3)
            try:
                letters.append(_image.rotate(angles[n], expand=True, resample=Image.BILINEAR))
            except:
                pass
        return letters

    @staticmethod
    def draw_image_from_letters(letters):
        result = Image.new('RGBA', (500, 150), 'white')
        positions = [10]
        for i, letter in enumerate(letters):
            width, height = letter.size
            result.paste(letter, (positions[-1], 0), mask=letter)
            positions.append(positions[-1] + width + 5)
        return result

    @staticmethod
    def get_image_from_url(url):
        request = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_4) AppleWebKit/537.36"
                          " (KHTML, like Gecko) Chrome/66.0.3359.139 Safari/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        })
        contents = urllib.request.urlopen(request).read()
        file = StringIO(contents)
        return Image.open(file)


class AmazonSolver(object):

    def __init__(self, spider, captcha_middleware):
        self.spider = spider
        self.captcha_middleware = captcha_middleware

    def input_captcha(self, response, spider):
        captcha_url = spider.get_captcha_key(response)
        solution = AmazonCaptchaSolver().solve_captcha(captcha_url)
        spider.log('Trying to solve captcha with url: {}, solution is: {}'.format(captcha_url, solution))
        return self.spider.get_captcha_form(
            response,
            solution=solution,
            referer=response.meta['initial_url'],
            callback=self.captcha_middleware.captcha_handled,
        ).replace(
            dont_filter=True
        )

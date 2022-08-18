import time


class TwoCaptchaSolver():

    TWOCAPTCHA_APIKEY = "e1c237a87652d7d330c189f71c00ec0b"

    INPUT_URL = 'http://2captcha.com/in.php'
    OUTPUT_URL = 'http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}'
    DELAY = 5
    MAX_RETRIES = 30

    def __init__(self, scraper, captcha_url, disable_log=False):
        self.scraper = scraper
        self.captcha_url = captcha_url
        self.add_lh_log('solve captcha from {}'.format(captcha_url))

    def extract_first(self, xpath_expr, default_value=None):
        data = self.scraper.tree_html.xpath(xpath_expr)
        return data[0] if data else default_value

    def add_lh_log(self, value):
        if self.scraper.lh:
            self.scraper.lh.add_list_log('errors', value)

    def send_request(self, data):
        for _ in range(3):
            req = self.scraper._request(
                self.INPUT_URL,
                verb='post',
                data=data
            )
            if req.status_code == 200:
                status = req.text.strip().split('|')[0]
                if status == 'OK':
                    captcha_server_id = req.text.strip().split('|')[-1]
                    return captcha_server_id
            else:
                self.add_lh_log('Can\'t upload captcha to server, status_code: {}'.format(req.status_code))
                print('Can\'t upload captcha to server, status_code: {}'.format(req.status_code))

    def get_captcha_answer(self, captcha_server_id):
        for _ in range(self.MAX_RETRIES):
            req = self.scraper._request(
                self.OUTPUT_URL.format(
                    api_key=self.TWOCAPTCHA_APIKEY,
                    captcha_id=captcha_server_id
                )
            )
            if req.status_code == 200:
                status = req.text.strip().split('|')[0]
                if status == 'OK':
                    answer = req.text.strip().split('|')[-1]
                    self.add_lh_log('Solution found')
                    print('Solution found')
                    return answer
                elif status == 'ERROR_CAPTCHA_UNSOLVABLE':
                    self.add_lh_log(status)
                    print('Can\'t solve captcha, server answer: {}'.format(status))
                else:
                    self.add_lh_log(status)
                    print('Captcha status: {}'.format(status))
                    time.sleep(self.DELAY)

    def recaptchaV2(self):
        site_key = self.extract_first('//div[@data-sitekey]/@data-sitekey')
        data = {
            "key": self.TWOCAPTCHA_APIKEY,
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": self.captcha_url
        }
        captcha_server_id = self.send_request(data)
        if captcha_server_id:
            answer = self.get_captcha_answer(captcha_server_id)
            return answer





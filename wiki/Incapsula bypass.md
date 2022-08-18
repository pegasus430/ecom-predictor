## How to find out what the site is using Incapsula? ##

## How to bypass Incapsula? ##

1. Copy headers with chrome debug tools ![Снимок экрана 2017-09-13 в 21.51.29.png](https://bitbucket.org/repo/e5zMdB/images/1670140330-%D0%A1%D0%BD%D0%B8%D0%BC%D0%BE%D0%BA%20%D1%8D%D0%BA%D1%80%D0%B0%D0%BD%D0%B0%202017-09-13%20%D0%B2%2021.51.29.png)
2. Assemble an OrderedDict using the data above
3. Assign the data to self.headers variable
4. Disable REFERER_ENABLED and COOKIES_ENABLED
5. Set 2 as a priority to IncapsulaRequestMiddleware 
6. Enable USE_PROXIES and residential proxies (ask Jim or Arsenii)

# Example #


```
#!python

self.headers = OrderedDict(
    [('Host', ''),
     ('Accept-Encoding', 'gzip, deflate'),
     ('Accept-Language', 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4'),
     ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36'),
     ('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'),
     ('Connection', 'keep-alive')]
)
settings.overrides['USE_PROXIES'] = True
settings.overrides['REFERER_ENABLED'] = False
settings.overrides['COOKIES_ENABLED'] = False
middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
middlewares['product_ranking.custom_middlewares.IncapsulaRequestMiddleware'] = 2
```


## Implementation ##
Middlewares (/tmtext/product-ranking/product_ranking/custom_middlewares.py)

* IncapsulaRetryMiddleware 

* IncapsulaRequestMiddleware

CaselessOrderedDict (/tmtext/product-ranking/product_ranking/incapsula_headers.py)

## Sources ##
[Why ordering HTTP headers is important](https://gwillem.gitlab.io/2017/05/02/http-header-order-is-important/)

[Headers lose their order when passed to a DownloaderMiddleware](https://github.com/scrapy/scrapy/issues/223)
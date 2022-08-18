[TOC]

# What it is

It's a way to make page screenshots. You feed an URL and get the browser screenshot back.

# Requirements

PhantomJS, Selenium, Pillow.

# Input params

## Obligatory params

* product_url - URL to make a screenshot from (this field is called `url` on SQS)

* site_name - always url2screenshot_products (or url2screenshot on SQS)

## Optional params

* width - width of the browser window (1280 by default)

* height - height of the browser window (1024 by default)

* crop_top - top offset of the "crop" operation (0 by default)

* crop_left - left offset of the "crop" operation (0 by default)

* crop_width - width of the cropped image; should not exceed `width` param!

* crop_height - hegiht of the cropped image; should not exceed `height` param!

* timeout - page load timeout (in seconds; 30 by default)

* user_agent - User-Agent header ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 (KHTML, like Gecko) Chrome/15.0.87" by default)

* driver - a browser to use, can be "firefox" or "chromium", or "random"; if not given - the default one is "chromium" 

* code_200_required - by default it's ON - the spider will return an empty response if the page you passed in `product_url` returned an HTTP code != 200. This helps to avoid making screenshots of invalid pages such as 503 "not available" etc.

## Captcha recognition

Spider automatically recognizes Amazon captchas and solves them.


## Command-line example:

```
scrapy crawl url2screenshot_products -a product_url="http://yandex.ru" -a width=1280 -a height=1024 -a crop_width=1280 -a crop_height=800 -a timeout=15 -a user_agent="Mozilla" -o /tmp/yandex.jl
```

## SQS example

```
{
    "server_name": "blahblahserver",
    "task_id":"153139",
    "site":"url2screenshot",
    "url": "http://google.com/404",
    "cmd_args": {
        "width": 1024,
        "height": 768,
        "user_agent": "googlebot"
    }
}
```

# User-Agents

If you receive an empty result file, make sure the user-agent you use is not banned on the website you're scraping. The spider already has a good user agent so if you're in doubts, try not to pass user-agent at all.

# Output data

The output .JL file is very similar to the existing SC ranking spiders' one. But it contains only 2 fields:

* url - the URL you passed (or the final page after redirects, if any)

* image - base64-encoded binary image data (PNG file). Take it, decode back, and save to any binary file - and you'll get the PNG screenshot as file.

# Cache

Please note that the outputs are cached in SQS by default. The cache can be controlled just as the normal SC ranking tasks.

# Live servers (real-time screenshots)

There are 2 servers hosting a live installations of this spider:

* sc-tests.contentanalyticsinc.com

* screenshot-scraper.contentanalyticsinc.com

Example of the rendered image: http://screenshot-scraper.contentanalyticsinc.com/get_img_data?spider=url2screenshot&url=http://kohls.com

Example of the "raw" results data (the same format as per SQS):
http://screenshot-scraper.contentanalyticsinc.com/get_raw_data?spider=url2screenshot&url=http://amazon.com/dp/B00HEYJ08S

Credentials: alex / 6DnDXPp5

Usually, the response comes in less than 20 seconds. But the solution is not very reliable because of it's nature - headless browsers are not very reliable, especially on micro instances with limited CPU and RAM.

If you see any issues, try to refresh the page. If it doesn't help, please contact me.

# Popups closing

There's a possibility to close popups such as this: https://bugzilla.contentanalyticsinc.com/attachment.cgi?id=4243

It works only for known popups, so it isn't a very reliable solution. But it seems to be the only way to get rid of popups on screenshots.

Send an extra `close_popups=1` arg to the spider (in `cmd_args`) if you want to enable this feature.
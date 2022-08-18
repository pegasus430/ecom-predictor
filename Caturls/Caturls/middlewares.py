# Importing base64 library because we'll need it ONLY in case if the proxy we are going to use requires authentication
import base64
import json
 
# Start your middleware class
class ProxyMiddleware(object):
    def __init__(self):
        proxydatafile = open("proxy_data.jl", "r")
        line = proxydatafile.readline()
        proxydata = json.loads(line)
        self.proxyurl = proxydata['url']
        self.proxyport = proxydata['port']
        proxydatafile.close()

    # overwrite process request
    def process_request(self, request, spider):
        if spider.use_proxy:
            # Set the location of the proxy
            request.meta['proxy'] = "http://%s:%s" % (self.proxyurl, self.proxyport)

            # Use the following lines if your proxy requires authentication
            proxy_user_pass = "USERNAME:PASSWORD"
            # setup basic authentication for the proxy
            encoded_user_pass = base64.encodestring(proxy_user_pass)
            request.headers['Proxy-Authorization'] = 'Basic ' + encoded_user_pass
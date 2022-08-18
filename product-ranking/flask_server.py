#
# Use for debugging only!
# Usage: just open a web-browser and type http://localhost:5000/get_data?url=http://www.amazon.in/Philips-AquaTouch-AT890-16-Shaver/dp/B009H0B8FU
#

import os
import sys
import json
import urlparse
import cgi
import subprocess
import tempfile
import time
import urllib

from flask import Flask, jsonify, abort, request
app = Flask(__name__)

CWD = os.path.dirname(os.path.abspath(__file__))
from monitoring.deploy_to_monitoring_host import find_spiders

ajax_template = """
<html>
<head>
  <script src="https://ajax.googleapis.com/ajax/libs/jquery/2.1.4/jquery.min.js"></script>

  <script>
  !function($){

	"use strict";

  	$.fn.jJsonViewer = function (jjson) {
	    return this.each(function () {
	    	var self = $(this);
        	if (typeof jjson == 'string') {
          		self.data('jjson', jjson);
        	}
        	else if(typeof jjson == 'object') {
        		self.data('jjson', JSON.stringify(jjson))
        	}
        	else {
          		self.data('jjson', '');
        	}
	      	new JJsonViewer(self);
	    });
  	};

	function JJsonViewer(self) {
		var json = $.parseJSON(self.data('jjson'));
  		self.html('<ul class="jjson-container"></ul>');
  		self.find(".jjson-container").append(json2html([json]));
	}


	function json2html(json) {
		var html = "";
		for(var key in json) {
			if (!json.hasOwnProperty(key)) {
				continue;
			}

			var value = json[key],
				type = typeof json[key];

			html = html + createElement(key, value, type);
		}
		return html;
	}

	function encode(value) {
		return $('<div/>').text(value).html();
	}

	function createElement(key, value, type) {
		var klass = "object",
        	open = "{",
        	close = "}";
		if ($.isArray(value)) {
			klass = "array";
      		open = "[";
      		close = "]";
		}
		if(value === null) {
			return '<li><span class="key">"' + encode(key) + '": </span><span class="null">"' + encode(value) + '"</span></li>';
		}
		if(type == "object") {
			var object = '<li><span class="expanded"></span><span class="key">"' + encode(key) + '": </span> <span class="open">' + open + '</span> <ul class="' + klass + '">';
			object = object + json2html(value);
			return object + '</ul><span class="close">' + close + '</span></li>';
		}
		if(type == "number" || type == "boolean") {
			return '<li><span class="key">"' + encode(key) + '": </span><span class="'+ type + '">' + encode(value) + '</span></li>';
		}
		return '<li><span class="key">"' + encode(key) + '": </span><span class="'+ type + '">"' + encode(value) + '"</span></li>';
	}

	$(document).on("click", '.jjson-container .expanded', function(event) {
    	event.preventDefault();
    	event.stopPropagation();
    	$(this).addClass('collapsed').parent().find(">ul").slideUp(100);
  	});

	$(document).on('click', '.jjson-container .expanded.collapsed', function(event) {
  		event.preventDefault();
  		event.stopPropagation();
  		$(this).removeClass('collapsed').parent().find(">ul").slideDown(100);
	});

}(window.jQuery);
</script>
<style>
.jjson-container {
    font-size: 13px;
    line-height: 1.2;
    font-family: monospace;
    padding-left: 0;
    margin-left: 20px;
}
.jjson-container,
.jjson-container ul{
    list-style: none !important;
}
.jjson-container ul{
    padding: 0px !important;
    padding-left: 20px !important;
    margin: 0px !important;
}

.jjson-container li {
    position: relative;
}

.jjson-container > li  > .key,
.jjson-container .array .key{
    display: none;
}

.jjson-container .array .object .key{
    display: inline;
}

.jjson-container li:after {
    content: ",";
}

.jjson-container li:last-child:after {
    content: "";
}

.jjson-container .null{
    color: #999;
}
.jjson-container .string{
    color: #4e9a06;
}
.jjson-container .number{
    color: #a40000;
}
.jjson-container .boolean{
    color: #c4a000;
}
.jjson-container .key{
    color: #204a87;
}
.jjson-container .expanded{
    cursor: pointer;
}

.jjson-container .expanded:before{
    content: "-";
    font-size: 16px;
    width: 13px;
    text-align: center;
    line-height: 13px;
    font-family: sans-serif;
    color: #933;
    position: absolute;
    left: -15px;
    top: 3px;
}

.jjson-container .collapsed:before{
    content: "+";
    font-size: 14px;
    color: #000;
    top: 1px;
}

.jjson-container li .collapsed ~ .close:before {
    content: "... ";
    color: #999;
}
</style>
</head>
<body>
  <h4>Spider: <span id="spider">{{ spider }}</span> (use "spider" GET param to change)</h4>
  <h4>URL: <span id="url">{{ url }}</span></h4>
  <p>
    <pre id="result" class="jjson">
      PROCESSING URL, PLEASE WAIT. DO NOT REFRESH THE PAGE.
    </pre>
  </p>
  <script>
    $.ajax({
      url: "/get_data_ajax",
      method: "GET",
      data: {url: $('#url').text(), spider: $('#spider').text()},
      success: function(result){
        $("#result").html(result);
        //alert( JSON.parse($("#result").html()) );
        $(".jjson").jJsonViewer( JSON.parse($("#result").html()) );
      }
    });
  </script>
</body>
</html>
"""

fcgi_template = '''
<!DOCTYPE html>
<html>
    <head lang="en">
        <meta charset="UTF-8">
        <title>Reload fcgi</title>
    </head>
    <body>
        <form method="post" action="">
            <button type="submit">Reload</button>
        </form>
    </body>
</html>
'''


def _find_spider_by_url(url):
    given_domain = urlparse.urlparse(url).netloc.replace('www.', '')
    all_spiders = find_spiders(os.path.join(CWD, 'product_ranking', 'spiders'))
    all_spiders = [[s[0], s[1]] for s in all_spiders if len(s) == 2]
    for spider_name, spider_domains in all_spiders:
        for s_domain in spider_domains.split(','):
            s_domain = s_domain.strip().replace('www.', '')
            if s_domain == given_domain:
                return spider_name


def _get_all_spidernames():
    all_spiders = find_spiders(os.path.join(CWD, 'product_ranking', 'spiders'))
    all_spiders = [[s[0], s[1]] for s in all_spiders if len(s) == 2]
    return [s[0] for s in all_spiders]


def run(command, shell=None):
    """ Run the given command and return its output
    """
    out_stream = subprocess.PIPE
    err_stream = subprocess.PIPE

    if shell is not None:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream, executable=shell)
    else:
        p = subprocess.Popen(command, shell=True, stdout=out_stream,
                             stderr=err_stream)
    (stdout, stderr) = p.communicate()

    return stdout, stderr


def check_running_instances(marker):
    """ Check how many processes with such marker are running already"""
    processes = 0
    output = run('ps aux')
    output = ' '.join(output)
    for line in output.split('\n'):
        line = line.strip()
        line = line.decode('utf-8')
        if marker in line and not '/bin/sh' in line:
            processes += 1
    return processes


def _start_spider_and_wait_for_finish(spider, url, close_popups=False, max_wait=60*2):
    """ Returns output data file name """
    output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jl')
    try:
        output_file.close()
    except:
        pass
    close_popups = ' ' if not close_popups else ' -a close_popups=1 '
    # production or local machine?
    if os.path.exists('/home/web_runner/virtual-environments/web-runner/bin/scrapy'):
        cmd = ('cd /home/web_runner/repos/tmtext/product-ranking;'
               ' /home/web_runner/virtual-environments/web-runner/bin/scrapy'
               ' crawl {spider} -a product_url="{url}" -o {output} -a image_copy=/tmp/_img_copy.png'
               ' {close_popups} '
               ' > /tmp/_flask_server_scrapy.log 2>&1')
    else:
        cmd = ('scrapy crawl {spider} -a product_url="{url}" -o {output}'
               ' -a image_copy=/tmp/_img_copy.png'
               ' {close_popups} '
               ' > /tmp/_flask_server_scrapy.log 2>&1')
    if isinstance(url, unicode):
        url = url.encode('utf8')
    try:
        url = urllib.unquote(url)
    except Exception as e:
        return str(e)
    _cmd = cmd.format(spider=spider, url=url, output=output_file.name, close_popups=close_popups)
    print('Executing spider command: %s' % _cmd)
    run(_cmd)
    _total_slept = 0
    while 1:
        _total_slept += 1
        time.sleep(1)
        if os.path.exists(output_file.name) and check_running_instances('-o '+output_file.name) == 0:
            # spider created file and stopped; successfully finished?
            return output_file.name
        if _total_slept > max_wait:
            return


@app.route('/get_data_ajax')
def get_data_ajax():
    url = request.args.get('url', '').strip()
    if isinstance(url, unicode):
        url = url.encode('utf-8')
    spider = request.args['spider'].strip()
    close_popups = request.args.get('close_popups', '').strip()
    print 'SPIDER', spider
    print 'PROCESSING URL', url
    output_fname = _start_spider_and_wait_for_finish(spider, url, close_popups)
    if output_fname:
        content = [json.loads(l.strip()) for l in open(output_fname, 'r').readlines()
                   if l.strip()]
        #content = {'URL': url, 'SPIDER': spider, 'DATA': content}
    else:
        content = {'ERROR': 'spider execution timeout (the spider has been running for too long)'}
    return cgi.escape(json.dumps(content))


@app.route('/get_data', methods=['GET'])
def get_data():
    url = request.args.get('url', '').strip()
    spider = request.args.get('spider', '').strip()
    # Parse additional argument from url and skip static arguments
    skip_args = ['url', 'spider']
    add_args_to_url = []
    for arg in request.args:
        if arg in skip_args:
            continue
        value = request.args.get(arg, '').strip()
        if value:
            add_args_to_url.append('{}={}'.format(arg, value))
        else:
            add_args_to_url.append(arg)
    if add_args_to_url:
        url += '&'
        url += '&'.join(add_args_to_url)
    # End parse url
    if not spider:
        spider = _find_spider_by_url(url)
    if isinstance(spider, (str, unicode)):
        if not '_products' in spider:
            spider = spider + '_products'
    if spider not in _get_all_spidernames():
        return 'Invalid spider name. Allowed: <br><br> %s' % '<br>'.join(sorted(_get_all_spidernames()))
    if not url:
        return 'Invalid URL param given (use "url" GET param)'
    return ajax_template.replace('{{ url }}', url).replace('{{ spider }}', spider)  # django-like templates =)


@app.route('/get_raw_data', methods=['GET'])
def get_raw_data():
    url = request.args.get('url', '').strip()
    spider = request.args.get('spider', '').strip()
    close_popups = request.args.get('close_popups', '').strip()
    if not spider:
        spider = _find_spider_by_url(url)
    if isinstance(spider, (str, unicode)):
        if not '_products' in spider:
            spider = spider + '_products'
    if spider not in _get_all_spidernames():
        return 'Invalid spider name. Allowed: <br><br> %s' % '<br>'.join(sorted(_get_all_spidernames()))
    if not url:
        return 'Invalid URL param given (use "url" GET param)'
    if isinstance(url, unicode):
        url = url.encode('utf-8')
    print 'SPIDER', spider
    print 'PROCESSING URL', url
    output_fname = _start_spider_and_wait_for_finish(spider, url, close_popups)
    if output_fname:
        return open(output_fname).read()


@app.route('/get_img_data', methods=['GET'])
def get_img_data():
    data = get_raw_data()
    try:
        j = json.loads(data)
    except Exception as e:
        return "Error while loading json: " + str(e)
    if not 'image' in j:
        return '"image" field not found in output data'
    return '<img alt="Embedded Image" src="data:image/png;base64,%s" />' % j['image']


@app.route('/fcgi', methods=['GET', 'POST'])
def fcgi():
    file_path = '/tmp/reload_uwsgi.ini'
    if request.method == 'POST':
        cmd = 'touch %s' % file_path
        os.system(cmd)
    return fcgi_template


if __name__ == "__main__":
    app.run(debug=True)
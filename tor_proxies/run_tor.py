#
# Creates a bunch of TOR proxies, and HTTP interfaces to them
# TOR and polipo must be installed!
# Don't forget to open IPs for proxies in firewall
#

import os
import sys
import time


CWD = os.path.dirname(os.path.abspath(__file__))

BASE_SOCKS_PORT = 21100
BASE_HTTP_PORT = 22100
NUM_PROXIES = 300
TOR_BINARY = '/usr/sbin/tor'

if __name__ == '__main__':
    data_dir = os.path.join(CWD, '_tor_data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    skip_tor = False
    if len(sys.argv) >= 2:
        if sys.argv[1].lower() != 'only_polipo':
            skip_tor = True

    if not skip_tor:
        fh_tor = open(os.path.join(CWD, 'tor.txt'), 'w')

        for i in xrange(NUM_PROXIES):
            socks_port = BASE_SOCKS_PORT + i

            data_dir2 = os.path.join(data_dir, str(socks_port))
            if not os.path.exists(data_dir2):
                os.makedirs(data_dir2)

            pid = '/tmp/tor_proxy_pid_%i' % i

            print 'starting TOR at port', i, 'pid /tmp/tor_proxy_pid_%i' % i
            tor_cmd = (
                '{TOR_BINARY} --RunAsDaemon 1 --CookieAuthentication 0 '
                '--HashedControlPassword "" '
                '--PidFile {pid} --SocksPort {socks_port}'
                ' --DataDirectory {data_dir2} &'.format(**locals())
            )
            print tor_cmd
            os.system(tor_cmd)

            fh_tor.write('socks5://127.0.0.1:%i\n' % (BASE_SOCKS_PORT+i))

        fh_tor.close()

    # wait for TOR circuits to complete
    print 'WAIT FOR POLIPO PROCESSES TO START!'
    time.sleep(60)

    fh_http = open(os.path.join(CWD, 'http.txt'), 'a')

    # run polipo-based proxies
    config_template = open(os.path.join(CWD, 'polipo_config.tpl')).read()
    for i in xrange(NUM_PROXIES):
        current_http_port = BASE_HTTP_PORT+i
        current_socks_port = BASE_SOCKS_PORT+i
        # prepare config
        new_config = config_template\
            .replace('[[PROXY_ADDRESS]]', '0.0.0.0')\
            .replace('[[PROXY_PORT]]', str(current_http_port))\
            .replace('[[PARENT_PROXY]]', 'localhost:%s' % current_socks_port)\
            .replace('[[PARENT_PROXY_TYPE]]', 'socks5')
        with open('/tmp/_polipo_config_%i' % i, 'w') as fh_cfg:
            fh_cfg.write(new_config)

        os.system(
            "/usr/bin/nohup /usr/bin/polipo -c /tmp/_polipo_config_%i &"
            " >> /tmp/_polipo_log_%i" % (i, i)
        )
        fh_http.write('http://127.0.0.1:%i\n' % current_http_port)

    fh_http.close()

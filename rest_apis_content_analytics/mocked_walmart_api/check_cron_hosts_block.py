#
# Check that walmart domains are blocked in /etc/hosts, and block if needed.
# Must be ran as root!
#

import os
import tempfile


BLOCK_LINE = ('127.0.0.1 marketplace.walmartapis.com walmartapis.com'
              ' www.walmartapis.com walmart.com www.walmart.com')


def _check_hosts():
    with open('/etc/hosts', 'r') as fh:
        content = fh.read()
    result = BLOCK_LINE in content
    return result


def _add_block_to_hosts():
    with open('/etc/hosts', 'a') as fh:
        fh.write('\n' + BLOCK_LINE + '\n')


if __name__ == '__main__':
    if not _check_hosts():
        _add_block_to_hosts()

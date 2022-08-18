#!/usr/bin/env python2.5

"""
Usage: %prog [options] file1 [file2] [extra_files] destination

Downloads a file (or files) via SFTP.

Example: sftp_download.py --host=sftp.example.com --path=/path/to/file/
         --username=monetate --password=PaSsWoRd download_me.xml
         download_me_too.xml /destination/

"""

from optparse import OptionParser
import os
import sys

import pexpect

######################### parameters &amp; settings ########################

parser = OptionParser(usage=__doc__.strip())

parser.add_option('--host', dest='host', action='store', type='string',
                  help='SFTP host')
parser.add_option('--path', dest='path', action='store', type='string',
                  help='SFTP path')
parser.add_option('--username', dest='username', action='store', type='string',
                  help='SFTP login username')
parser.add_option('--password', dest='password', action='store', type='string',
                  help='SFTP login password')

############################### functions ##############################

def download_files(files, destination, host, path, username, password):
    """
    Log in to the SFTP server using the username and password
    provided and download the specified files.
    """
    sftp_opts = ['-o', 'PasswordAuthentication=yes',
                 '%s@%s' % (username, host)]
    p = pexpect.spawn('sftp', sftp_opts)
    p.logfile = sys.stdout

    try:
        p.expect('(?i)password:')
        x = p.sendline(password)
        x = p.expect(['Permission denied','sftp&gt;'])
        if x == 0:
            print 'Permission denied for password:'
            print password
            p.kill(0)
        else:
            x = p.sendline('cd ' + path)
            for file in files:
                x = p.expect('sftp&gt;')
                x = p.sendline('get ' + file + ' ' + destination)
            x = p.expect('sftp&gt;')
            x = p.isalive()
            x = p.close()
            retval = p.exitstatus
    except pexpect.EOF:
        print str(p)
        return 'SFTP file transfer failed due to premature end of file.'
    except pexpect.TIMEOUT:
        print str(p)
        return 'SFTP file transfer failed due to timeout.'

############################## main block ##############################

if __name__ == '__main__':
    '''
    options, args = parser.parse_args()
    if not args:
        parser.print_help()
        sys.exit(1)
    destination = args[-1]
    files = args[:-1]
    '''
#    status = download_files(files, destination, options.host, options.path,
#                            options.username, options.password)

    status = download_files("marketplace_and_wmt_items_ip_mkt_2015-09-20.xml.gz", "/home/mufasa/Documents/Workspace/Content Analytics/Misc/Download via SFTP/", "54.175.228.114", "/walmart/",
                            "sftp", "SelbUjheud")

    sys.exit(status)
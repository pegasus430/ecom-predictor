#
# Parallel version of bulk_sc_pages_scraper.py
#

import os
import sys
import json
import argparse
import subprocess
import time
import threading
import random
import tempfile


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('spider', type=str,
                        help='Spider name')
    parser.add_argument('file', type=str,
                        help='Input file to read URLs from')
    parser.add_argument('output', type=str,
                        help='Output file to write URLs to')
    parser.add_argument('parallel', type=int,
                        help='Number of spiders running in parallel')
    args = parser.parse_args()
    return args


def split_source_file(fname, num_parts):
    """ Splits the given filename into `num_parts`
        Returns array of part filenames """
    # first, get the number of lines
    num_lines = sum(1 for _ in open(fname, 'r'))
    lines_per_part = num_lines / num_parts + 100
    os.system('split -l {lines_per_part} "{fname}" "{output}"'.format(
        lines_per_part=lines_per_part, fname=fname, output=fname+'_PART_'))
    fname_dir = os.path.abspath(os.path.dirname(fname))
    files_in_dir = os.listdir(fname_dir)
    return sorted([os.path.abspath(f) for f in files_in_dir if fname+'_PART_' in f])


def parse_url_parallel(spider, url, output_fh, callback):
    _output_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jl')
    _output_file.close()
    _output_file = _output_file.name
    _log_file = tempfile.NamedTemporaryFile(delete=False, suffix='.log')
    _log_file.close()
    _log_file = _log_file.name
    os.system('scrapy crawl %s -a product_url="%s" -o "%s" -s LOG_FILE="%s"' % (
        spider, url, _output_file, _log_file))
    with open(_output_file) as fh:
        lines = [l.strip() for l in fh.readlines() if l.strip()]
    if not lines:
        with open(_log_file, 'r') as fh_log:
            log_content = fh_log.read()
        os.remove(_output_file)
        os.remove(_log_file)
        return callback('ERROR|%s|LOG|%s' % (url, log_content.replace('\n', '\t')), output_fh)
    line = json.loads(lines[0])
    line['given_url'] = url
    output_content = json.dumps(line)
    os.remove(_output_file)
    os.remove(_log_file)
    callback(output_content, output_fh)


def _on_parse_url_parallel_exit(output_content, output_fh):
    output_fh.write(output_content + '\n')


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


if __name__ == '__main__':
    args = parse_args()
    # block proxies
    os.system('echo 1 > /tmp/_stop_proxies')
    # block marketplaces
    os.system('echo 1 > /tmp/_stop_marketplaces')

    # get parts
    file_parts = split_source_file(args.file, args.parallel)
    file_contents = [[l.strip() for l in open(fp).readlines() if l.strip()] for fp in file_parts]
    output_files = [open(f+'_scraped_output', 'w') for f in file_parts]

    for line_i in xrange(len(file_contents[0])):  # first file is always the biggest

        for input_fname_i, _ in enumerate(file_parts):
            input_fname = file_parts[input_fname_i]
            output_fh = output_files[input_fname_i]
            try:
                input_url = file_contents[input_fname_i][line_i]
            except IndexError:
                continue

            if line_i % 100 == 0:
                print 'Processing line %i of input file %s' % (line_i, input_fname)

            t = threading.Thread(
                target=parse_url_parallel, args=(args.spider, input_url, output_fh,
                                                 _on_parse_url_parallel_exit))
            t.daemon = True
            t.start()

            #result_content = parse_url_parallel(args.spider, input_url)
            #output_fh.write(result_content + '\n')

            #if line_i % 10 == 0:
            #    output_fh.flush()

        while check_running_instances(marker='scrapy crawl'):
            time.sleep(1)  # wait for the spiders to finish
        [fh_.flush() for fh_ in output_files]

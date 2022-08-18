import fnmatch
import os
import bz2
import json
import time
import stat


def is_plain_json_list(fname):
    if not os.path.exists(fname):
        return -1
    with open(fname, 'r') as fh:
        cont = fh.read(1024)
    cont = cont.strip()
    if not cont:
        return True
    return cont[0] == '{'


def unbzip(f1, f2):
    # check that the file is empty
    with open(f1, 'rb') as fh:
        cont = fh.read()
    if not cont:
        with open(f2, 'wb') as fh:
            fh.write(cont)
        return False
    # unarchive
    try:
        f = bz2.BZ2File(f1)
        cont = f.read()
    except:
        return False
    f.close()
    with open(f2, 'wb') as fh:
        fh.write(cont)
    return True


def change_buyer_reviews(line):
    line = line.strip()
    if not 'average_rating' in line:
        return line  # nothing to fix
    try:
        line = json.loads(line)
    except:
        return
    br = line.get('buyer_reviews', '')
    if not br:
        return line  # nothing no fix
    num_of_reviews = br.get('num_of_reviews', 0)
    average_rating = br.get('average_rating', 0)
    rating_by_star = br.get('rating_by_star', {})
    line['buyer_reviews'] = [num_of_reviews, average_rating, rating_by_star]
    return json.dumps(line)


def validate_2_lines(line1, line2):
    try:
        line1 = json.loads(line1)
        line2 = json.loads(line2)
    except:
        return
    line1.pop('buyer_reviews')
    line2.pop('buyer_reviews')
    return line1 == line2


def change_br_in_file(fname):
    with open(fname, 'r') as fh:
        lines = fh.readlines()
    lines_replaced = [change_buyer_reviews(line) for line in lines]
    if len(lines_replaced) != len(lines):
        print 'arrays length mismatch!'
        return
    for i in range(len(lines)):
        if not validate_2_lines(lines[i], lines_replaced[i]):
            print 'lines mismatch'
            return
    with open(fname, 'w') as fh:
        for line in lines_replaced:
            fh.write(line.strip()+'\n')


def file_age_in_seconds(pathname):
    return time.time() - os.stat(pathname)[stat.ST_MTIME]


def fix_double_bzip_in_file(fname):
    if not is_plain_json_list(fname):
        print 'File [%s] compressed, decompressing...' % fname
        result1 = unbzip(fname, fname)
        iters = 0
        while result1:
            result1 = unbzip(fname, fname)
            iters += 1
            if iters > 1:
                print '  RECURSIVE BZIP DETECTED', fname


def compress_and_rename_old(fname):
    if is_plain_json_list(fname) == -1:
        return  # file does not exists?
    if not is_plain_json_list(fname):
        return  # compressed already
    if not is_plain_json_list(fname):
        return  # compressed already
    #if file_age_in_seconds(fname) < 2*86400:
    #    return  # not old
    os.system('bzip2 "%s"' % fname)
    os.rename(fname+'.bz2', fname)
    print '  File compressed:', fname


def fix_double_bzip_in_dir(d, min_age, max_age):
    for root, dirnames, filenames in os.walk(d):
        for filename in fnmatch.filter(filenames, '*.jl'):
            full_name = os.path.join(root, filename)
            if not os.path.isfile(full_name):
                continue
            if file_age_in_seconds(full_name) < min_age:
                continue
            if file_age_in_seconds(full_name) > max_age:
                continue
            fix_double_bzip_in_file(full_name)
            with open(full_name, 'rb') as fh:
                cont = fh.read()
            if len(cont) > 15:  # do not compress empty (?) files
                compress_and_rename_old(full_name)


if __name__ == '__main__':
    DIR = '/home/web_runner/virtual-environments/scrapyd/items/product_ranking/amazon_products/'
    BACKUP_DIR = '/home/ubuntu/amazon_products/'
    FIX_DOUBLE_BZIP_DIR = '/home/web_runner/virtual-environments/scrapyd/items/product_ranking/'
    MIN_AGE = 0#86400
    MAX_AGE = 86400*15

    os.system('sudo chmod 777 -R "%s"' % FIX_DOUBLE_BZIP_DIR)

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        cmd = 'cp %s* %s' % (DIR, BACKUP_DIR)
        print cmd
        os.system(cmd)

    fix_double_bzip_in_dir(FIX_DOUBLE_BZIP_DIR, MIN_AGE, MAX_AGE)

    matches = []
    for root, dirnames, filenames in os.walk(DIR):
        for filename in fnmatch.filter(filenames, '*.jl'):
            matches.append(os.path.join(root, filename))

    print 'Found %i files totally' % len(matches)
    for m in matches:
        if not is_plain_json_list(m):
            if is_plain_json_list(m) == -1:
                continue
            print 'File [%s] compressed, decompressing...' % m
            result1 = unbzip(m, m)
            while result1:
                result1 = unbzip(m, m)
                print '  RECURSIVE BZIP DETECTED', m
            change_br_in_file(m)
        compress_and_rename_old(m)
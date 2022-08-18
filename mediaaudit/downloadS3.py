import traceback
import boto3
import os
import magic
import re
import logging

from boto.s3.key import Key
from boto.s3.connection import S3Connection
from compareAPI import call_endpoint

logger = logging.getLogger('mediaaudit')

bucket_name = 'rich-media-audit'
bucket_id = 'AKIAINLDEBFPZ44YXXOQ'
key = 'YHnIzCDHEmOkXJ6mO8Y7Z+Md/T3j451L6+jHahcZ'

client = boto3.client(
    's3',
    aws_access_key_id=bucket_id,
    aws_secret_access_key=key
)

ourConnection = S3Connection(bucket_id, key)
ourBucket = ourConnection.get_bucket(bucket_name)


def upload(filename, uploadName):
    with open(filename, "rb") as imageFile:
        f = imageFile.read()
        b = bytearray(f)

        mime = magic.Magic(mime=True)
        mimetype = mime.from_file(filename)

        client.put_object(Bucket=bucket_name, Body=b, ContentType=mimetype, Key=uploadName)


def getComparison(filename, seasons, orientation, actual_url):
    """ if no s3 image existed for seasons+orientation returns -1 """
    s3_pattern = 'https://s3.amazonaws.com/{}/{}'
    result = -1
    for season in seasons:
        name = season + str(filename) + orientation + ".jpg"
        k = Key(ourBucket, name)

        if k.exists():
            s3_url = s3_pattern.format(bucket_name, name)
            try:
                result = call_endpoint(s3_url, actual_url)
                # sometimes generated url point to different product.
                # if we have 50% match assume that this needed product image
                if result > 50:
                    return result
            except Exception as e:
                logger.error('Image comparison api error. Url1 = {0}. Url2 = {1}'.format(s3_url, actual_url))
                logger.error(e.message)
                continue
    logger.info('Image match not processing due errors or missed S3 image. Returning 0.')
    return result


# this will probably be the most useful. Takes a folder and for every SCENE7 image in that folder,
# it will upload that image to AmazonS3 with name: season + PC9 + orientation + .jpg
def uploadFromDirectory(directory, quiet=False, remove_uploaded=False):
    fail_counter = 0
    success_counter = 0
    filenames = os.listdir(directory)

    for filename in filenames:
        try:
            name = format_name(filename)
            if not name:
                raise ValueError('Can\'t parse filename {}'.format(filename))

            if not quiet:
                print('Starting upload file {}'.format(name))

            upload(os.path.join(directory, filename), name)

            success_counter += 1
            print('Successfully uploaded {} of {} files'.format(success_counter, len(filenames)))

            if remove_uploaded:
                if not quiet:
                    print('Removing local file {}'.format(os.path.join(directory, filename)))
                deleteLocally(os.path.join(directory, filename))
        except:
            fail_counter += 1
            print('Failed {} of {} files to upload. Filename {}'.format(fail_counter, len(filenames), filename))
            if not quiet:
                print(traceback.format_exc())
    if not quiet:
        print('Done. Uploaded {}. Failed {}.'.format(success_counter, fail_counter))


def listAll():
    for key in getSet():
        print key.name.encode('utf-8')


def getSet():
    return ourBucket.list()


def delete(filename):
    # if True is passed in, then we clear the entire bucket
    if isinstance(filename, bool):
        if filename:
            for i in getSet():
                i.delete()
    else:
        k = Key(ourBucket, filename)
        k.delete()


def download(filename, destination):
    client.download_file(bucket_name, filename, destination)


def getUrl(filename):
    ourString = 'https://{}.s3.amazonaws.com/{}'.format(bucket_name, filename)

    return ourString


def deleteLocally(localName):
    os.remove(localName)


def format_name(original_name):
    # 17_H1_Dockers_men_27316-0007_side.jpg
    name = re.search(r'(16|17)_(H1|H2).+?([\d]{5})-([\d]{4}).+?(front|back|side|F|B|S).{0,}\.jpg', original_name, re.IGNORECASE)
    if name:
        season = 'S' if name.group(2) == 'H1' else 'F'
        season += name.group(1)
        pc9tag = name.group(3) + name.group(4)
        orientation = name.group(5)[0].upper()
        return season + pc9tag + orientation + '.jpg'

    # L_F17_women_35879_0002_B_ws.jpg
    name = re.search(r'(F16|S16|S17|F17).+?([\d]{5})_?([\d]{4}).+?(front|back|side|F|B|S).{0,}\.jpg', original_name, re.IGNORECASE)
    if name:
        season = name.group(1)
        pc9tag = name.group(2) + name.group(3)
        orientation = name.group(4)[0].upper()
        return season + pc9tag + orientation + '.jpg'


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage='usage: usage: %prog [options] directory')
    parser.add_option(
        '-q', '--quiet',
        dest='quite',
        default=False,
        action='store_true',
        help='don\'t print output messages'
    )
    parser.add_option(
        '-r', '--remove-uploaded',
        dest='remove_uploaded',
        default=False,
        action='store_true',
        help='remove uploaded file from directory'
    )

    (options, args) = parser.parse_args()

    if len(args) < 1:
        parser.error('wrong number of arguments')

    directory = args[0]
    if not os.path.isdir(directory):
        parser.error('wrong path to directory')

    uploadFromDirectory(
        directory,
        quiet=options.quite,
        remove_uploaded=options.remove_uploaded
    )
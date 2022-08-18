# Comparing Media API #

Last updated Feb 28, 2017

# Overview #

This API is to take in two URLs pointing to two forms of media (image, video) and return how well they match.
It takes in two media files and returns the percent they match. For example, two images that only differ by a background or two images that differ by only a minor crop will both return high match values. The image comparison function are divided in 2 function:

1. adjusted_compare(first, second): This method takes in two parameters (the file names of two image files) and compares them. This is the one that will return high values even for a minor difference such as a different background.

2. exact_compare(first, second): This method just takes in two parameters and returns a raw match.

The video comparison function are divided in 2 function:

1. extract_frames(video, prefix=''): This method takes in video file and make 3 image files(first, middle, and last image from the video) from it.

2. compare_videos(first, second): This method just takes in two parameters and returns a raw match.

# API endpoints #

## Image Comparison ##

Allowed image types: JPEG

Required params:

* media_type: 'image'
* first_url
* second_url
* compare_method: 'local' or 'base'

Optional params:

* trim_fuzz: float value

Adjusted Compare : 
```
#!python

http://mediacompare.contentanalyticsinc.com/compare?media_type=image&compare_method=local&first_url={url1}&second_url={url2}
```

Adjusted Compare with TrimFuzz: 
```
#!python

http://mediacompare.contentanalyticsinc.com/compare?media_type=image&compare_method=local&first_url={url1}&second_url={url2}&trim_fuzz={trimFuzz}
```

Exact Compare : 

```
#!python

http://mediacompare.contentanalyticsinc.com/compare?media_type=image&compare_method=base&first_url={url1}&second_url={url2}
```

Exact Compare with TrimFuzz: 

```
#!python

http://mediacompare.contentanalyticsinc.com/compare?media_type=image&compare_method=base&first_url={url1}&second_url={url2}&trim_fuzz={trimFuzz}
```

Here is useful information about TrimFuzz.
http://code.runnable.com/VQ5WVo8OIogZ-_hv/trim-image-edge-whitespace-with-fuzz-for-python

The second_url parameter could be single url or listed urls. 
For Example : 
```
#!python

# Compare image without TrimFuzz
http://mediacompare.contentanalyticsinc.com/compare?media_type=image&compare_method={compare_method}&first_url={url1}&second_url[]=url1&second_url[]=url2&second_url[]=....

# Compare image with TrimFuzz
http://mediacompare.contentanalyticsinc.com/compare?media_type=image&compare_method={compare_method}&first_url={url1}&second_url[]=url1&second_url[]=url2&second_url[]=....&trim_fuzz={trimFuzz}
```

## Video Compare ##

Required params:

* media_type: 'video'
* first_url
* second_url

```
#!python

http://mediacompare.contentanalyticsinc.com/compare?media_type=video&first_url={url1}&second_url={url2}
```
The second_url parameter could be single url or listed urls. 
For Example : 
```
#!python

http://mediacompare.contentanalyticsinc.com/compare?media_type=videofirst_url={url1}&second_url[]=url1&second_url[]=url2&second_url[]=....

```

# Sample Output #

Response is JSON. Fields:

* error: true or false. Read 'message' field if error occurred
* message: contains text with error description 
* result: comparison result in %
* first_url: used url for comparison
* second_url: used url for comparison. 

Successfully Compared :

```
#!python

# Result for single url compare
{
  "error": false, 
  "first_url": "https://c1.staticflickr.com/9/8529/8673547142_ee80080ae5_b.jpg", 
  "message": null, 
  "result": 100.00062500381742, 
  "second_url": "https://c1.staticflickr.com/9/8529/8673547142_ee80080ae5_b.jpg"
}


# Result for listed url compare
[
  {
    "error": false, 
    "first_url": "https://c1.staticflickr.com/9/8529/8673547142_ee80080ae5_b.jpg", 
    "message": null, 
    "result": 100.00062500381742, 
    "second_url": "https://c1.staticflickr.com/9/8529/8673547142_ee80080ae5_b.jpg"
  }, 
  {
    "error": false, 
    "first_url": "https://c1.staticflickr.com/9/8529/8673547142_ee80080ae5_b.jpg", 
    "message": null, 
    "result": 57.36211047005153, 
    "second_url": "http://cliparts.co/cliparts/dT4/5bB/dT45bB5kc.jpg"
  }
]
```

An Error occured :
```
#!python

# Response code 200
{
  "error": true, 
  "message": "The media file from second_url https://c1.staticflickr.com/9/8529/8673547142_ee8008.jpg is no longer available", 
  "result": null, 
  "second_url": "https://c1.staticflickr.com/9/8529/8673547142_ee8008.jpg"
}

# Response code 400
{
  "error": true, 
  "message": "Missing params: second_url", 
  "result": null
}

```

# HTTP Basic auth #

username: user  
password: tE3OqHDZPk

# Pre-installed applications #

wand

decorator

six

validators

numpy

cycler

matplotlib

pyparsing

python-dateutil

pytz

# Server updating #

```
#!bash

cd /var/web/tmtext/
git pull
sudo docker restart api_media_compare_18
```
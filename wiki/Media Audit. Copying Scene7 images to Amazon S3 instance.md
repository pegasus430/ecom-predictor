# Overview #

We have images stored in Scene7. We need to scrape them from Scene7 and place on our server (Amazon S3 instance).


# Running #
To run it go to source code directory and just run RMAuploader.py script:

```
#!bash

$ python ./mediaaudit/RMAuploader.py

```
Logs will be available at *./mediaaudit/scene7_scraper.log*. It's rotating logging with max file size 1Mb (when it will reach 1Mb value it will rename current logfile to *./mediaaudit/scene7_scraper.log.1* and start new one).

# How it works #
We have predefined folders for scanning:

```
#!python

folder_list = [
    "LevisPortal/Wholesale/Dockers/2017 Fall/",
    "LevisPortal/Wholesale/Dockers/2016 Fall/",
    'LevisPortal/Wholesale/Dockers/2017 Spring/',
    'LevisPortal/Wholesale/Dockers/2016 Spring/',
    'LevisPortal/Wholesale/Levis/2016 Fall/Men/',
    'LevisPortal/Wholesale/Levis/2016 Fall/Women/',
    'LevisPortal/Wholesale/Levis/2016 Spring/Mens/',
    'LevisPortal/Wholesale/Levis/2016 Spring/Womens/',
    'LevisPortal/Wholesale/Levis/2017 Spring/Men/',
    'LevisPortal/Wholesale/Levis/2017 Spring/Women/',
    'LevisPortal/Wholesale/Levis/2017 Fall/Women/',
    'LevisPortal/Wholesale/Levis/2017 Fall/Men/',
]
```
To scrape different folders you need to change that list in script (folders paths should be exactly how they are on Scene7).
Script taking each folder in list and sending SOAP request to Scene7 to get list of images on that folder. For now it wont include subfolders and it will take only 5000 items (more than 5000 items will be returned with pagination and it's not implemented yet).
Then we working on each image one by one:

* Download it locally

* Format name for S3 instance (season + pc9 + orientation + '.jpg')

* Upload it to S3

* Remove local file

For name formatting we use few regular expressions:

```
#!python

    # 17_H1_Dockers_men_27316-0007_side.jpg
    name = re.search(r'(16|17)_(H1|H2).+?([\d]{5})-([\d]{4}).+?(front|back|side|F|B|S).{0,}\.jpg', original_name, re.IGNORECASE)
    ...
    ...
    ...
    # L_F17_women_35879_0002_B_ws.jpg
    name = re.search(r'(F16|S16|S17|F17).+?([\d]{5})_?([\d]{4}).+?(front|back|side|F|B|S).{0,}\.jpg', original_name, re.IGNORECASE)
    ...
    ...
    ...
```
If downloaded image will not match to any of those rules it will be skipped.
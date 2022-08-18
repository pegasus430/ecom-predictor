## Auditor.py Documentation ##

The Auditor.py file will be the interface used to run all of the Auditors. 


```
#!python

def initialize(website, input, output):
    if website == 'Kohls':
        crawlerAux.run(input, output)
    else if website == 'Macys':
        MacysAudit.main(input, output)
    else if website == 'JCPenny':
        JCPenny2.run(input, output)
```

initialize takes in 3 parameters- a website type, the name of the input mapping as a string, and the name of the output mapping you would like to write to as a string.

## Auditors Documentation ##

General documentation for all of the Auditors. Note that of the 3, the Macys Auditor has been tested the least rigorously. 


```
#!python

def loadWorkBook(name):
```
loadWorkBook takes in the mapping file and loads in data from it. Note that this method expects the Sheet name to be 'Sheet1'. That field, however, can be easily modified.


```
#!python

def scrape(): 
```
scrape calls the Scraper helper function that reads in URLs extracted from the mapping and parses information from those URLs. 


```
#!python

def compare():

```
compare uses the results that we scraped and compares them using the Comparison API. 


```
#!python

def writeToFile(output):

```
writeToFile writes the results of the audit to the file specified by output and saves it.

## compareAPI documentation ##

```
#!python

def callEndpoint(url1, url2):
```
Calls API Endpoint using two URLs. Returns compare value of the two URLs or error.

## downloadS3.py Documentation ##

```
#!python

def uploadUrl(url):
```
Uploads the data contents of that URL to Amazon S3.



```
#!python

def upload(filename, uploadName):
```
Uploads actual byte array of the file to AmazonS3. Within the bucket, file is renamed as whatever the 'uploadName' parameter takes on within. This method also makes that file URL accessible. 



```
#!python

def getComparison(filename, seasons, orientation, actualURL):
```

Takes in the filename (generally PC9), all the desired seasons, expected orientation of picture, and the URL of the image to compare to. Returns either an error or an integer comparison value.


```
#!python
def uploadFromDirectory(directory):

```
Takes in directory name as a string and uploads every image within that directory to AmazonS3. Note that this method makes assumptions about the format of each filename (as long as every file is downloaded from Scene7, this won't be a problem) and uploads each file like: season+PC9+orientation.


```
#!python
def listAll():

```
Prints the filename of every file in the bucket. 


```
#!python

def getSet():
```
Returns list of all filenames in bucket.


```
#!python

def delete(filename):
```
Deletes a certain file from bucket. If the boolean value of True is passed in instead, the bucket will be cleared. 


```
#!python

def download(filename, destination):
```
Downloads file named filename into destination. 


```
#!python

def getUrl(filename):
```
Generates URL pointing to object in the bucket.


```
#!python

def deleteLocally(localName1):
```
Deletes local file.

## scraperAux Files ##

This documentation applies to all of the scraperAux files since they are all very similar. 


```
#!python

def getUrls(url, color, retry, productID):
```
Generates URLs of main (front) images. 


```
#!python

def getAltURLS(url, retry, productID):
```
Generates URLs of alt (side and back) images.


```
#!python

def getAltURLSFull(url, retry, productID):
```
Helper method for generating all alt urls. 


```
#!python

def filter(entry):
```
Filters out repeats and garbage URLS.
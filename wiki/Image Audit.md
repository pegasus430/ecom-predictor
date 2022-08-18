# Image Audit #

## Scene 7 Image Import and PC9>WebID Mapping ##

Have someone download all possible files to use into internal ftp server.

For reference, in Scene7, there is a Description field that contains the PC9 and the Color info (see attached screenshot):
Login: https://s7sps1.scene7.com/IpsWeb/IpsWeb.jsp
User: graham@contentanalyticsinc.com
Pwd: levislevis

Photos are located in Wholesale>>Levis folder? "2016 Fall" is most current. Also include 1 season back "2016 Spring". Export both folders, naming current season folder as "Current Season", and last season folder as "Last Season".

QUESTIONS: Are alternate views for different colors in scene7, how are they stored?

For every product that Levi's wants to crawl on a given site, we need a PC9 to Web ID mapping. This is the mapping file that will tell us:
1. Which products to crawl using the Web ID.
2. How to map the product we crawl back to the images from scene7

QUESTIONS: Can Levi's provide us with a sample of what this file will look like.

## Crawl ##

1. For every Web ID, crawl that product. Save all 3 f/b/s images to a file with the correct PC9_# filename (#####_####_0, #####_####_1, #####_####_2).
2. Crawl the alternate colors, and save those as WebID_F. 
3. Check to see if Alt Image; Video; Size Chart; Fit Guide exist on page. Save results to new database with each UPC as row.

## Compare ##

We have built out the ability to compare a group of images to a group of images. First try to compare to "This season" folder, if no images exist, check if images exist from "Last season" folder.

Save comparison success to UPC database.


## Generate Audit ##

Brand Audit elements: Front, Back, Side Images; Alt Image; Video; Size Chart; Fit Guide
Log this information into an excel spreadsheet.

Attach sample output.

## Insights Report UI ##
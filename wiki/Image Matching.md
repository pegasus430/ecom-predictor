Use Cases, in order of priority

## 1) Reduce false positive matches ##

Use image matching, e.g. between product images on Walmart and an item on Amazon, to reduce false positive matches. This could go into confidence score that takes into account multiple factors such as title, price, and image. Only needed in cases where confidence/score is, say between 50 - 90. 

Example of product page: http://www.walmart.com/ip/Better-Homes-and-Gardens-16-Cube-Organizer-Wall-Unit-Multiple-Colors/34455891

Product image: http://i.walmartimages.com/i/p/11/13/04/62/08/1113046208155_215X215.jpg

Before worrying about scale, try this on an arbitrary sample of, say 500 items with confidence scores between 50 - 90. Then, manually go through and see if this really helps reduce false positive matches. (Long term if we have enough items/images, we could use this to improve matches, not just reduce false positives.)

Why this should work: Ecommerce sites often use the same manufacturer stock product images, so they are a good way to detect if 2 products are the same.

## 2) Given a product on one site (walmart.com), does the same product on another site (amazon.com) use the same product image(s). If so, we want to know that.
 ##
This is similar to the above. But instead of using image matching to help with matching, we are determining whether the same product (that we have high confidence is a match on another site) has duplicate (the same) image(s) on the other site.

This would be included as an optional field(s) in the *_matches files. If this option is specified, then for each match, include the total number of duplicated images on the secondary site, and the links of the matching images, e.g. site1/image1,site2/image1, site1/image2, site2/image2 etc. 

## 3) Consumer search by uploaded image or URL. ## 

Given an image upload or URL, find the corresponding product on Walmart.com, Amazon.com, etc. This would have to be callable via an API such that it could be used from a web site, by third parties, or a mobile app. 

a) Looking for exact matches. Scenario is -- user finds an image of a product on the web and wants to buy it, but can't find the product. They can put in the URL and find the product and buy it. 

b) Looking for close matches, perhaps based on common points -- likely use case is mobile application, scanning front of a book, DVD, cereal box -- basics; more complex items would be bicycles, furniture, etc. 

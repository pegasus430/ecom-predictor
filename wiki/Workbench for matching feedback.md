This page describes the usage of the matching workbench service. Its goal is to gather human feedback regarding if 2 products on different sites are the same product or not, with the purpose of evaluating and improving automatic product matching.

# Location

    http://54.164.95.0:8080/workbench

# Source     
    tmtext/workbench_matching

# Login

* user: `test`
* pass: `632316f5ecdb9bba3b7c55b570911aaf`

# Usage

The service asks the user to evaluate whether the 2 products seem to be the same product or not, by means of Yes/No questions.

The most important question to be answered is this one:

**Are these the same product?**

You should answer "Yes" if it seems like the 2 products look like the exact same product (if they are similar but some properties differ, such as number of inches for TVs etc, they should be considered different products).

Besides this main question, there are some additional questions about each of the product's features, which you should answer as best as you can, or leave unanswered if it is too unclear what the answer should be.

When you are done, you can click the "Next" button at the right side of the page and you will be shown another product.

If you need to skip a product you can also click "Next" without filling in any of the answers.


## Sample answers

Below are some examples of products and what answers I would give for each question:

1.
http://www.walmart.com/ip/30253411 and http://www.amazon.com/Personalized-Protective-Hardshell-Hardcover-Samsung/dp/B00QGXUQDG


* Are these the same product? - No
* Does the manufacturer/brand match? - No (*Yo Gabba Gabba* vs *Cassoula*)
* Does the product image match (is the same product depicted, with only minor differences)? - No
* Does the product name match (is it fairly similar)? - No

2.
http://www.walmart.com/ip/36276773 and http://www.amazon.com/Ten-Strawberry-Street-Whittier-Square/dp/B00HM9OBSE

* Are these the same product? - Yes
* Does the manufacturer/brand match? - Yes (*10/Ten Strawberry Street*)
* Does the product image match (is the same product depicted, with only minor differences)? - Yes
* Does the product name match (is it fairly similar)? - they match but there are minor differences (first name contains "Nova" and the second doesn't. I would leave unanswered or answer "Yes")


3.
http://www.walmart.com/ip/14872619 and http://www.amazon.com/Bankers-Box-Drawer-Steel-Storage/dp/B00N3ACMDM

* Are these the same product? - Yes
* Does the manufacturer/brand match? - Yes (*Bankers Box*)
* Does the product image match (is the same product depicted, with only minor differences)? - No (main image is different)
* Does the product name match (is it fairly similar)? - Yes (they are mostly the same but expressed differently)

4.
http://www.walmart.com/ip/37253379 and http://www.amazon.com/Trident-Case-Electra-Wireless-Charging/dp/B00HYPC5XY

* Are these the same product? - Yes
* Does the manufacturer/brand match? - Yes (*Trident (Case)* - it is not identical but obviously refers to the same manufacturer)
* Does the product image match (is the same product depicted, with only minor differences)? - Yes
* Does the product name match (is it fairly similar)? - there are some differences so it is not exactly the same name, but it doesn't clearly refer to different products either. I would leave unanswered or answer "No"

5.
http://www.walmart.com/ip/17467089 and http://www.amazon.com/Wilton-2105-2061-Fire-Truck-Pan/dp/B0000A1OHH

* Are these the same product? - the image looks the same but the manufacturer is different. I would leave unanswered or answer "No"
* Does the manufacturer/brand match? - No (*Wilton* vs *Shindigz*)
* Does the product image match (is the same product depicted, with only minor differences)? - Yes
* Does the product name match (is it fairly similar)? - No (one is "Wilton Fire Truck Pan", which could be something different than simply "Fire Truck Pan")

6.
http://www.walmart.com/ip/23888904 and http://www.amazon.com/Cobra-MicroTalk-CX102A-Channel-Walkie/dp/B00FOR82L8

* Are these the same product? - Yes
* Does the manufacturer/brand match? - Yes (*Cobra*)
* Does the product image match (is the same product depicted, with only minor differences)? - Yes (the objects are identical, they are just positioned differently)
* Does the product name match (is it fairly similar)? - No

# Errors / problems

In case you encounter any errors or have questions, please contact Ana at ana.uban@gmail.com

Thank you!
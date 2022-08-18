http://www.top500guide.com/top-500/the-top-500-list/

# Overview #

The purpose of this data collection is to generate a report: The Top 100 Most Social eCommerce Companies

This should be based on, in a given period (e.g. Jul 1, 2013 - Jul 31, 2013):

* Number of Tweets
* Number of YouTube videos
* Number of Blog posts

# Implementation #

* To start, build 2 crawlers, one for Twitter, one for YouTube. Later we will build the blog crawler. The crawler should take a date range as input, e.g. 7-01-2013,7-31-2013 and a data list file (see below)

* The Twitter crawler should retrieve:
- The number of tweets published by a given company for each day, during the period
- The total number of tweets published by a given company during the period
- The total number of tweets
- Total number of followers

* The YouTube Crawler should count the number of videos published on YT by a given company:
- Each day during the period
- In total during the period
- Number of views for each video published during the period
- Total number of views for all videos published during the period

* All of this goes into a data file, something like:

You can count the number of tweets, e.g. at https://twitter.com/Amazon
You can count the number of videos, e.g. at http://www.youtube.com/user/amazon/videos

As input, take a data file containing the list of Companies,Internet500Rank,Twitter,YouTube

```

Internet500Rank,CompanyName,Twitter,YouTube
1,Amazon.com,@Amazon,amazon
2,Staples.com,@Staples,staples
3,Apple.com,@itunestrailers @iTunesMusic,apple
4,Walmart.com,@walmart,walmart
5,Dell,Dell,@dell,dell
6,Office Depot,@officedepot,OfficialOfficeDepot
7,HSN.com,@hsn,hsn
8,Sears,@sears,sears
9,Netflix,@netflix,NewOnNetflix
10,CDW,@CDWCorp,CDWPeopleWhoGetIT
11,Best Buy,@bestbuy,bestbuy
12,Office Max,@officemax,officemax
13,New Egg,@newegg,newegg
14,Macy's,@macys,macys
15,W.W. Grainger,@grainger,wwgraingerinc
16,Sony Electronics,@sony,sonyelectronics
17,Costco,@CostcoTweets,
18,LL Bean,@LLBean,llbean
19,Victoria's Secret,@VictoriasSecret,VICTORIASSECRET
20,J.C. Penney Co,@jcpenney,

```

# Usage #

The Youtube crawler is found under MostSocialCompanies/youtube_crawler.py

It can be run with the period as an argument, like this:

    python youtube_crawler.py --date1 <minimum_date> --date2 <maximum_date>

**Example**

    python youtube_crawler.py --date1 2013-06-01 --date2 2013-08-01


# Tools #

The crawler uses the 

* Youtube Data API, you will need the [google-api-python-client](http://code.google.com/p/google-api-python-client/) library installed on your machine to run it.

* wrapper around Twitter API, you will need the [python-twitter](http://code.google.com/p/python-twitter/) library installed on your machine to run it.

# Output #

The crawler generates a csv file, with a day given time interval on each line, with the following fields:
(It will contain on each line a date and info corresponding to that date. Days with no activity will not be logged.)

* Date - the day in the interval corresponding to current line
* Brand - the brand the Youtube channel belongs to
* Followers, Following, Tweets, All_Tweets - Twitter data, to be implemented
* YT_Videos - dictionary containing titles of Youtube videos published on that day and view counts for each of them
* YT_All_Videos - the total number of Youtube videos published by the brand's channel in the interval
* YT_All_Views - total number of views for videos published in the given interval by the brand's channel
* Tweets - number of tweets published on the day in the current line, by Brand's user
* All_Tweets - total number of tweets published in the time interval by Brand's user
* Following - total number of users Brand's user is following
* Followers - total number of followers for Brand's user

A sample output file can be found in `sample_output/MostSocialCompanies.csv`(for the command in the example above)
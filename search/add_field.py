import csv
import sys
import json

# jet url key, value is remainder of the input row, as dictionary (like csvreader returns it)
jet_to_all = {}
# with open("/home/ana/code/tmtext/data/jetcom/" + \
#     "upc_Jet_Amazon_Walmart_Analysis_Categories_Merged_Coupons_2015_08_24_REV10.02.2015_V1_Cross_Zip_Code_Jetcom_Comparison.csv") as inf:
with open("/home/ana/code/tmtext/data/jetcom/" + \
    "upc_Jet_Amazon_Walmart_Analysis_Categories_Merged_Coupons_2015_08_24_REV10.02.2015_V1_Cross_Zip_Code_Jetcom_Comparison_new3_06102015.csv") as inf:    

    reader = csv.DictReader(inf, delimiter=',', quoting=csv.QUOTE_MINIMAL)
        
    while True:
        try:
            data = next(reader)
            jet_url = data['URL']
            # if jet_url in jet_to_all:
            #     if (not data['Walmart.com UPC Match']) and jet_to_all[jet_url]['Walmart.com UPC Match']:
            #         continue
            jet_to_all[jet_url] = data
        except StopIteration:
            break

csvout = open('/home/ana/code/tmtext/data/jetcom/merged.csv', 'wb')

first = True

with open("/home/ana/code/tmtext/data/jetcom/" + \
    "upc_Jet_Amazon_Walmart_Analysis_Categories_Merged_Coupons_2015_08_24_REV10.02.2015_V1_Cross_Retailer_Price_Comparison_additional_upcs.csv") as inf:    

    reader = csv.DictReader(inf, delimiter=',', quoting=csv.QUOTE_MINIMAL, quotechar='"')
        
    while True:
        try:
            data = next(reader)
            jet_url = data['URL']
            try:
                old_data = jet_to_all[jet_url]
            except Exception:
                sys.stderr.write("NO KEY " + jet_url + "\n")
                old_data = {}
                            
            # res = [old_data["Product name"],
            #     old_data["URL"],
            #     old_data["Amazon.com URL"],
            #     old_data["Jet.com Price"],
            #     old_data["Jet.com discount"],
            #     old_data["Jet.com Reported Amazon price"],
            #     old_data["Amazon.com Actual Price"],
            #     old_data["Amazon.com First Party Seller"],
            #     old_data["Amazon Prime"],
            #     old_data["Top level Jet Category"],
            #     old_data["Next level Jet Category"],
            #     old_data["Bottom level Jet Category"],
            #     old_data["Top level Amazon Category"],
            #     old_data["Next level Amazon Category"],
            #     old_data["Bottom level Amazon Category"],
            #     old_data["Amazon UPC"],
            #     old_data["Model number"],
            #     old_data["Amazon ASIN"],
            #     old_data["Jet In Stock"],
            #     old_data["Delivery in"],
            #     old_data["Amazon In Stock"],
            #     old_data["Am.Prime Pantry"],
            #     old_data["Am.Subscribe-and-Save"],
            #     old_data["Jet UPC"]] + \
            #     [data['Walmart.com URL'], data['Walmart.com Price'], data['Walmart.com Match Confidence'], data['Walmart.com UPC Match']]
                # [data['Match_URL'], data['Target_Price'], data['Confidence'], data['UPC_match']]
            
            # add all old data to new data
            # old_data.update(data)

            # 
            # add just one new data field to new data
            # if not data['Jet UPC']:
            #     data['Jet UPC'] = old_data['Jet UPC']
            # if data['URL'] != old_data['URL']:
            #     continue
            if data['Walmart.com UPC Match'] == '0':
                data['Walmart.com Price'] = ''
            old_data = data

            #
            # # missing fields:
            # old_data['Jet.com Reported Amazon price'] = ''

            # old_data['Jet In Stock'] = old_data['94107-Jet In Stock']
            # old_data['Jet.com discount'] = old_data['94107-Jet.com discount']
            # old_data['Delivery in'] = old_data['94107-Delivery in']
            # old_data['Product name'] = old_data['Walmart']


            print ",".join(map(lambda x: json.dumps(x).encode("utf-8"), old_data.values()))
            if first:
                spamwriter = csv.DictWriter(csvout, delimiter=',',quotechar='"', quoting=csv.QUOTE_MINIMAL, 
                    # fieldnames = ['Product_Name','Original_URL','Match_URL','UPC','Confidence','UPC_match','Model_match'])
                    # fieldnames = old_data.keys())
                    fieldnames = 
                    # ["Product name",
                    # "URL",
                    # "Amazon.com URL",
                    # "Jet.com Price",
                    # "Jet.com discount",
                    # "Jet.com Reported Amazon price",
                    # "Amazon.com Actual Price",
                    # "Amazon.com First Party Seller",
                    # "Amazon Prime",
                    # "Top level Jet Category",
                    # "Next level Jet Category",
                    # "Bottom level Jet Category",
                    # "Top level Amazon Category",
                    # "Next level Amazon Category",
                    # "Bottom level Amazon Category",
                    # "Amazon UPC",
                    # "Model number",
                    # "Amazon ASIN",
                    # "Jet In Stock",
                    # "Delivery in",
                    # "Amazon In Stock",
                    # "Am.Prime Pantry",
                    # "Am.Subscribe-and-Save",
                    # "Jet UPC",
                    # 'Walmart.com URL',
                    # 'Walmart.com Price',
                    # 'Walmart.com Match Confidence',
                    # 'Walmart.com UPC Match'])
                    # 


                    ['Amazon ASIN','URL','Jet.com Reported Amazon price','Am.Subscribe-and-Save','Jet UPC','Jet.com discount',\
                    'Model number','Next level Amazon Category','Amazon UPC','Product name','Top level Amazon Category','Bottom level Jet Category',\
                    'Amazon.com First Party Seller','Walmart.com UPC Match','Jet.com Price','Amazon.com URL','Walmart.com URL',\
                    'Bottom level Amazon Category','Jet In Stock','Top level Jet Category','Amazon In Stock',\
                    'Walmart.com Price','Walmart.com Match Confidence','Amazon Prime','Delivery in','Amazon.com Actual Price',\
                    'Am.Prime Pantry','Next level Jet Category'],\
                    extrasaction = 'ignore')

                    # ['Walmart','URL','Amazon.com URL','Amazon Coupon Amount','94107-Jet.com Price','75201-Jet.com Price','02116-Jet.com Price', \
                    # '94107-Jet.com discount','75201-Jet.com discount','02116-Jet.com discount','Amazon.com Actual Price','Amazon.com First Party Seller', \
                    # 'Amazon Prime','Top level Jet Category','Next level Jet Category','Bottom level Jet Category','Top level Amazon Category',\
                    # 'Next level Amazon Category','Bottom level Amazon Category','Amazon UPC','Model number','Amazon ASIN','94107-Jet In Stock',\
                    # '75201-Jet In Stock','02116-Jet In Stock','94107-Delivery in','75201-Delivery in','02116-Delivery in','Amazon In Stock',\
                    # 'Am.Prime Pantry','Am.Subscribe-and-Save','Jet UPC'])
                    


                spamwriter.writeheader()

            # spamwriter.writerow(old_data)
            spamwriter.writerow(old_data)

            first = False

        except StopIteration:
            break
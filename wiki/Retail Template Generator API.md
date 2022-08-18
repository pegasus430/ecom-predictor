# Generic API for Retail Template Generator

## Overview

ALL conversion will be done using the mapping file. Therefore, all content will be exported that exists for each product being exported for a given retailer. Then, the API would use the mapping file to put that data into the template file. Then, even if the short description is a different part of the page for Walmart and Amazon, the mapping would tell the short description to go to the right column no matter what.

If you are on the target.com tab, then the targetTemplate will be the value sent to the API. This will call the correct file from a folder of all retailer templates, and the correct row in the mapping file.

Note: Eventually, we could support only exporting the fields that are "submitting changes".

## REST API 

Will exist on bulk-import server

1) convert(retailerTemplate, inputFile) is called by PHP when export is clicked in UI. It passes the retailer template the export is for, and all of the data that will be used by the API in the inputFile.

API uses retailerTemplate parameter to grab the correct row from the template file to convert to, and uses the inputFile to populate the template. The API then returns the template file with all data included.

Optional templates - https://docs.google.com/spreadsheets/d/1s1RudDWtKDVvdKUVtfo7oh0T3PejYbTJTgYayluVMeE/edit?usp=sharing

## Available columns being sent by PHP when generate retailer export is clicked
Columns available for the moment: 
 
* 'Tool id'                => 'tool_id',
* 'Upc'                    => 'upc',
* 'ASIN'                   => 'asin',
* 'Item Name'              => 'product_name',
* 'Describe the product'   => 'long_description',
* 'Directions'             => 'usage_directions',
* 'Ingredients'            => 'ingredients',
* 'Browse Keywords'        => 'browse_keyword',
* 'Safety Warnings'        => 'safety_warnings',
* 'Vendor Code/ID'         => 'vendor_code_id',
* 'Vendor Item/SKU Number' => 'vendor_item_sku_number',
* 'Comments'               => 'comments',
* 'Brand Name'             => 'brand',
* 'Indications'            => 'indications',
* 'Url'                    => 'url',
* 'Price'                  => 'price',
* 'Currency'               => 'currency',
* 'Description'            => 'description',
* 'Shelf Description'      => 'shelf_description',
* 'Created Date'           => 'created_date',
* 'Primary Seller'         => 'primary_seller',
* 'Category Name'          => 'category_name',
* 'GTIN'                   => 'gtin',
* 'TCIN'                   => 'tcin',
* 'Primary Image'          => 'images',
* 'Additional Images'      => 'images',
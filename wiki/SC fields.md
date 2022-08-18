# No longer used
* related_products
* _jcpenney_has_size_range

# To remove?
* **img_count #int** 
* **video_count #int** 
* **assortment_url #str** 
* **minimum_order_quantity #str (costco only)** 
* **shelf_name #str** 
* **shelf_path #list** 
* **sponsored_links #dict** 
* **seller_ranking #int** 

# In use (name #type)

## Misc
* model #str
* reseller_id #str
* locale #str
* bestseller_rank #int
* is_mobile_agent #bool
* limited_stock #bool
* last_buyer_review_date #str?
* response_code #int

## Product main information
* title #str
* url #str
* image_url #str
* description #str
* brand #str
* buyer_reviews #list
* variants #list
* marketplace #list
* department #str

## Categories
* category #str
* categories #list
* categories_full_info #list

## Questions
* date_of_last_question #?
* recent_questions #?
* all_questions #?

## Shipping
* shipping #?
* shipping_included #bool
* shipping_cost #str

## Barcodes
* dpci #str
* tcin #int
* sku #int
* upc #int
* asin #str

## Prices
* price #str
* price_with_discount #str
* price_subscribe_save #?
* price_original #?
* price_details_in_cart #bool
* special_pricing #bool

## Product status
* is_in_store_only #bool
* is_out_of_stock #bool
* no_longer_available #bool
* not_found #bool
* temporary_unavailable #bool
* available_online #bool
* available_store #bool

## Walmart only
* _walmart_redirected #bool
* _walmart_original_id #?
* _walmart_current_id #?
* _walmart_original_oos #bool remove?
* _walmart_original_price #str remove?
* low_stock #bool
* item_not_available #bool
* is_pickup_only #bool remove?
* shelf_page_out_of_stock #bool remove?

## Amazon only
* prime #str
* is_sponsored_product #bool

## Jet only
* deliver_in #str

## Samsclub only
* subscribe_and_save #int
* price_club #str
* price_club_with_discount #str

## Target only
* origin #bool

## Google only
* google_source_site #?

## Officedepot only
* search_redirected_to_product #bool

## Amazon top category
* target_url #bool
* target_category #?
* target_exists #bool
* walmart_url #str
* walmart_category #?
* walmart_exists #bool

## Pipelines
*  search_term_in_title_partial #bool
* search_term_in_title_exactly #bool
* search_term_in_title_interleaved #bool
* _subitem #bool
* _statistics #?
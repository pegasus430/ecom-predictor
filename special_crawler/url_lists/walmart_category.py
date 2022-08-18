"""
This tool get categories from Walmart API and separate all product urls into
different csv files

"""
from time import time, sleep
from pymongo import MongoClient,DESCENDING
import urllib2
import json
from multiprocessing import Pool
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.FileHandler('walmart.log')
handler.setLevel(logging.INFO)
# create a logging format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(handler)


def fill_items2db(filename="full_urls.csv"):
    #Load product urls into MongoDB
    db = MongoClient().walmart
    db['item'].ensure_index('item_id')
    db['item'].ensure_index('department')
    start_time = time()
    i=0
    for line in open(filename,"r"):
        i += 1
        url = line.strip()
        item_id = url.split("/")[-1]
        p = {'item_id':item_id}
        if i % 100000==0:
            print i,"Time :",time() - start_time, "seconds"
        p['url'] = url
        p['department'] = ''
        p['categoryPath'] = ''
        db['item'].insert(p)
    print db['item'].find().count()


def fill_category_db(api_keys,n=100000):
    #Fill out categories for products in MongoDB
    start_time = time()
    limit = len(api_keys)*n
    db = MongoClient().walmart
    cursor = db['item'].find({'department':{"$eq":''}}).limit(limit)
    itm = []
    lst = []
    i = 0
    for c in cursor:
        id = c['item_id']
        itm.append(id)
        if len(itm) >= n:
            lst.append((itm,api_keys[i]))
            i+=1
            itm=[]
    if len(itm)>0:
        lst.append((itm,api_keys[i]))
    for l in lst:
        print  len(l[0]),l[1]
    p = Pool(len(api_keys)+1)
    lstres = p.map(multi_run_wrapper,lst)
    print lstres
    print "Time :",time() - start_time, "seconds"


def multi_run_wrapper(args):
    #Wrapper for multiprocessing
    return get_categoryPath_db(*args)


def get_categoryPath_db(items,apikey):
    chunk=[]
    qr=sv = 0
    db = MongoClient().walmart
    start_time = datetime.datetime.now()
    st_time = time()
    j=0
    for id in items:
        j += 1
        if j % 1000 == 0:
            logger.info("Processed: %s %s %s",apikey,j,time()-st_time)
        chunk.append(id)
        if len(chunk)==20:
            d = datetime.datetime.now()-start_time
            if d.total_seconds() < 0.22:
                sleep(0.22-d.total_seconds())
            start_time = datetime.datetime.now()
            res = get_product_api(chunk,apikey)
            if len(res)==0:
                return apikey,qr,sv
            qr += 1
            chunk = []
            for r in res:
                p = {'item_id':str(r[0])}
                rec = db['item'].find_one(p)
                if rec != None:
                    rec['department'] = r[1].split("/")[0].strip()
                    rec['categoryPath'] = r[1]
                    db['item'].save(rec)
                    sv += 1
    if len(chunk) > 0:
        res=get_product_api(chunk,apikey)
        qr += 1
        for r in res:
            p = {'item_id':r[0]}
            rec = db['item'].find_one(p)
            if rec !=None:
                rec['department'] = r[1].split("/")[0].strip()
                rec['categoryPath'] = r[1]
                db['item'].save(rec)
                sv += 1
    return apikey,qr,sv


def get_product_api(itemlst,apikey=""):
    sp = ",".join(itemlst)
    res = []
    if apikey=='': apikey=apiKey
    try:
        url="http://api.walmartlabs.com/v1/items?ids=%s&apiKey=%s" % (sp,apikey)
      #  logger.info(url)
        response = urllib2.urlopen(url,timeout=15).read()
        dct = json.loads(response)
        if dct != None and dct.has_key('items'):
            for itm in dct['items']:
                if itm.has_key('itemId') and itm.has_key('categoryPath'):
                    res.append((itm['itemId'],itm["categoryPath"]))
    except Exception as ex:
        logger.info("Problem with: %s %s",apikey,ex)
        sleep(1)
    return res

def save_result(department):
    #Save result in csv file
    db = MongoClient().walmart
    cursor = db['item'].find({'department':department})
    folder = "separated/"
    i=0
    with open(folder + department+".csv","wb") as f:
        for c in cursor:
            if c.get('url','')!='':
                f.write(c['url']+"\n")
                i += 1
    print department,i
    return i

def separate_products():
    i=0
    for line in  open("department_list.csv","r"):
        dep = line.strip()
        i += save_result(dep)
    print i

def get_departments():
    #get list of department
    db = MongoClient().walmart
    cursor = db['item'].find({'department':{"$ne":''}}).distinct('department')
    i=0
    print cursor
    with open("department_list.csv","wb") as f:
        for c in cursor:
            f.write(c+"\n")
            i += 1
    print i

if __name__ == '__main__':
    #Load all product urls into MongoDB
    fill_items2db("full_urls.csv")

    #You should create 40 Walmart API accounts
#    api =[your 40 Walmart API keys]
    #Retrieve information about category from Walmart API and save it in MongoDB
    #This function will run 40 processes and will work 2-3 days
#    fill_category_db(api)

#   Create a list of departments
#   get_departments()

#   Separate all urls by departments
#    save_result("department_list.csv")
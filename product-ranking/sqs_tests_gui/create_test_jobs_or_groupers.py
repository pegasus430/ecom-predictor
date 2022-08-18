import random
import sys

import requests


sites = ['amazon', 'walmart']
url = 'http://52.1.192.8/add-job/'


args = {
    'site': random.choice(sites), 'quantity': 30,
}


if 'searchterms' in sys.argv:
    args['searchterms_str'] = 'water'
else:
    if args['site'] == 'amazon':
        args['product_url'] = random.choice([
            'http://www.amazon.com/Samsung-Galaxy-Tab-7-Inch-White/dp/B00J8DL78O/ref=sr_1_2?ie=UTF8&qid=1436210359&sr=8-2&keywords=samsung&pebp=1436210360927&perid=19JN29PAV2GTV0DS1SFJ',
            'http://www.amazon.com/Samsung-Galaxy-Unlocked-Android-Smartphone/dp/B00IUMNBGU/ref=sr_1_3?ie=UTF8&qid=1436210466&sr=8-3&keywords=samsung&pebp=1436210483163&perid=0R059C0VQXBH81RA6MQV',
            'http://www.amazon.com/Galaxy-Limited-Unlocked-International-Version/dp/B00YOI94ME/ref=sr_1_5?ie=UTF8&qid=1436210466&sr=8-5&keywords=samsung',
            'http://www.amazon.com/Samsung-G850a-Unlocked-Quad-Core-Smartphone/dp/B00UCJ0IBU/ref=sr_1_8?ie=UTF8&qid=1436210466&sr=8-8&keywords=samsung',
            'http://www.amazon.com/Samsung-Gear-Neo-Smartwatch-Warranty/dp/B00JBJ3I4Q/ref=sr_1_9?ie=UTF8&qid=1436210466&sr=8-9&keywords=samsung',
            'http://www.amazon.com/Samsung-LS27D85KTSR-GO-27-Inch-LED-Lit/dp/B00R61V7JE/ref=sr_1_13?ie=UTF8&qid=1436210466&sr=8-13&keywords=samsung',
        ])

    if args['site'] == 'walmart':
        args['product_url'] = random.choice([
            'http://www.walmart.com/ip/27677832?productRedirect=true',
            'http://www.walmart.com/ip/Pioneer-DDJ-SX2-DJ-Controller/43261738',
            'http://www.walmart.com/ip/Refurbished-Numark-Mixtrack-Pro-DJ-USB-MIDI-Software-Controller-w-Audio-I-O-Refurbished/43842938',
            'http://www.walmart.com/ip/NEW-ODYSSEY-CBM10E-Economy-Battle-Mode-Pro-DJ-Turntable-Mixer-Coffin-Black/39673095',
            'http://www.walmart.com/ip/Numark-DJ2GO-Portable-Dj-Controller-W-Usb/41082557',
            'http://www.walmart.com/ip/Numark-Red-Wave-DJ-Headphones/40577353'
        ])

print requests.post(url, data=args).text
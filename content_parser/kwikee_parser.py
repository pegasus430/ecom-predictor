import sys
import threading
import xlrd

headers = [
    'UPC',
    'Title',
    'Brand',
    'Short Description',
    'Long Description',
    'Special Features 1',
    'Special Features 2',
    'Special Features 3',
    'Special Features 4',
    'Special Features 5',
    'Usage Directions',
    'Ingredients',
    'Caution-Warnings-Allergy Statements',
    'Key Search Terms'
]


def setup_parse(content, dest):
    wb = xlrd.open_workbook(file_contents=content)
    sheet = wb.sheet_by_index(0)

    if not map(lambda c: c.value, sheet.row(0)) == headers:
        message = 'expected headers: ' + str(headers)
        raise ValueError(message)
    t = threading.Thread(target=parse, args=(sheet, dest))
    t.start()


def parse(sheet, dest):
    products_json = []

    # skip the first row
    for i in range(1, sheet.nrows):
        row = sheet.row(i)
        product_json = {
            'upc': row[0].value,
            'product_name': row[1].value,
            'brand': row[2].value,
            'description': row[4].value,
            'long_description': '<ul>'
        }
        for j in range(5, 10):
            product_json['long_description'] += '<li>' + row[j].value + '</li>'
        product_json['long_description'] += '</ul>'
        product_json['shelf_description'] = '<ul>'
        for j in range(6, 9):
            product_json['shelf_description'] += '<li>' + row[j].value + '</li>'
        product_json['shelf_description'] += '</ul>'
        product_json['usage'] = row[10].value
        product_json['ingredients'] = row[11].value.split(', ')
        product_json['warnings'] = row[12].value
        product_json['keywords'] = row[13].value.replace(';', ', ')
        products_json.append(product_json)
    print products_json
    # requests.post(dest, data=products_json, headers={'Content-Type': 'application/json'})

if __name__ == '__main__':
    parse(sys.argv[1], sys.argv[2])

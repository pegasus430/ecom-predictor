import csv, re, copy, sys

f = open(sys.argv[1], 'r')
reader = csv.reader(f)

f2 = open(sys.argv[2], 'w')
writer = csv.writer(f2)

#attributes_list = ['title', 'upc', 'brandName', 'categoryNamePath', 'productUrl', 'description', 'imageUrl', 'additionalImageUrls']

column_names = reader.next()

attributes_list = copy.copy(column_names)
attributes_list.remove('attributes')
attributes_list = filter(None, attributes_list)

output_column_names = []

for row in reader:
    product_url = row[column_names.index('productUrl')]
    try:
        domain_name = re.search('www.(.+\.com)', product_url).group(1)
    except:
        continue

    output_column_names.append(domain_name + '_attribute_name')
    output_column_names.append(domain_name + '_attribute_value')

    attributes = row[column_names.index('attributes')].split(';')
    for attribute in attributes:
        attribute_name = attribute.split('=')[0]
        
        if attribute_name[-1] == '_':
            attribute_name = attribute_name[:-1]

        if not attribute_name in attributes_list:
            attributes_list.append(attribute_name)

writer.writerow(output_column_names)

for a in attributes_list:
    output_row = [None] * len(output_column_names)

    # reset reader
    f.seek(0)
    reader.next()

    for row in reader:
        product_url = row[column_names.index('productUrl')]
        try:
            domain_name = re.search('www.(.+\.com)', product_url).group(1)
        except:
            continue

        attribute_name_column = output_column_names.index(domain_name + '_attribute_name')
        attribute_value_column = attribute_name_column + 1

        if a in column_names:
            output_row[attribute_name_column] = a
            output_row[attribute_value_column] = row[column_names.index(a)]

        else:
            attributes = row[column_names.index('attributes')].split(';')
            for attribute in attributes:
                attribute_name = attribute.split('=')[0]
                
                if attribute_name[-1] == '_':
                    attribute_name = attribute_name[:-1]

                if attribute_name == a:
                    output_row[attribute_name_column] = a
                    attribute_value = attribute.split('=')[1]
                    output_row[attribute_value_column] = attribute_value
                    break

    writer.writerow(output_row)

f.close()
f2.close()    

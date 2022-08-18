The purpose of this API is to populate a retailer template file with info from the MC database

It accepts a POST request at endpoint http://bulk-import.contentanalyticsinc.com/mc_export

The template mapping file and retailer template files for this API are stored in S3 bucket **retailer-template-files**

### Inputs ###
1. a csv file containing a column with header 'CAID'
2. arguments 'retailer' and 'server' (can be provided as url argument or in POST form)

Example using Python:

requests.post('http://bulk-import.contentanalyticsinc.com/mc_export?retailer=jet&server=mattel', files={'file': open('mattel-walmart-ids.csv', 'rb')})

### Custom template ###

Argument 'retailer' is optional.

Additional arguments:

* 'file_name' - file name to export.
* 'file_type' - optional file type, if omitted, determined based on file_name's extension.
* 'worksheet' - optional worksheet name, default is 'Custom'.
* 'field[]' or 'field[n]' - fields to export in desired order, n should start with 0 and shouldn't contain gaps.
* 'field_name[field]' - optional custom name for field.

### Output ###
A JSON response

Failure: (status 200, or 400 in case of user error)

```
#!json

{'error': True, 'message': error_message}
```

Success: (status 200)

```
#!json

{'error': False, 'file': export_file_name}
```

In success case, export_file_name corresponds to file of the same name in 'exports' directory of S3 bucket 'retailer-template-files'

### Process ###

1. The API pulls 'Template Mapping File.xlsx' from the bucket and looks for the provided retailer in the second column (Retailer)

2. If the retailer is found, then it uses the mapping between the headers in the template mapping file and the values in the retailer row to map the MC data to the headers in the retailer template file

3. It uses the 'server' argument to query that server and extract the MC info for each product ID in column 'CAID' in the provided file

4. It grabs the retailer's template file from the bucket and fills each row with the mapped info

5. It uploads the filled-out template file to S3 and returns JSON response as described above
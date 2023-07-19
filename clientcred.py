import json
import logging
import os
import sys
import adal,pyodbc
import struct

def turn_on_logging():
    logging.basicConfig(level=logging.DEBUG)
    #or,
    #handler = logging.StreamHandler()
    #adal.set_logging_options({
    #    'level': 'DEBUG',
    #    'handler': handler
    #})
    #handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))

parameters_file = (sys.argv[1] if len(sys.argv) == 2 else
                   os.environ.get('ADAL_SAMPLE_PARAMETERS_FILE'))

if parameters_file:
    with open(parameters_file, 'r') as f:
        parameters = f.read()
    sample_parameters = json.loads(parameters)
else:
    raise ValueError('Please provide parameter file with account information.')

authority_url = (sample_parameters['authorityHostUrl'] + '/' +
                 sample_parameters['tenant'])

#uncomment for verbose log
#turn_on_logging()

### Main logic begins
context = adal.AuthenticationContext(
    authority_url, api_version=None
    )

token = context.acquire_token_with_client_credentials(
    sample_parameters['resource'],
    sample_parameters['clientId'],
    sample_parameters['clientSecret'])
### Main logic ends

#print(json.dumps(token, indent=2))
accessToken = token["accessToken"]

SQL_COPT_SS_ACCESS_TOKEN = 1256 

connString = "Driver={ODBC Driver 17 for SQL Server};SERVER=yoursqldb.database.windows.net;DATABASE=yourdb"

exptoken = b''.join(b.to_bytes(2,'little') for b in bytes(accessToken['accessToken'], 'utf-8'))
tokenstruct = struct.pack("=i", len(exptoken)) + exptoken;

conn = pyodbc.connect(connString, attrs_before = { SQL_COPT_SS_ACCESS_TOKEN:tokenstruct});
cursor = conn.cursor()
cursor.execute("SELECT TOP 20 pc.Name as CategoryName, p.name as ProductName FROM [SalesLT].[ProductCategory] pc JOIN [SalesLT].[Product] p ON pc.productcategoryid = p.productcategoryid")
row = cursor.fetchone()
while row:
    print (str(row[0]) + " " + str(row[1]))
    row = cursor.fetchone()

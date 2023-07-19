# Using Azure AD Service Principals to connect to Azure SQL from a Python Application running in Linux

Yes, I know, that's a long headline for an article. But I found no other easy way to describe what I could find out over the last week.
All started with a customer trying to connect a Python application running in Linux to Azure SQL DB. This shouldn't be a problem if they could use SQL Authentication but Enterprises usually tend to user their Active Directory identities to have more control over access and so on. Learn more here:  https://www.microsoft.com/en-us/sql-server/developer-get-started/python/ubuntu/

It also would be OK if they had their identities in Azure AD only, we could use simple Active Directory Password authentication and everything would work fine (Authentication=ActiveDirectoryPassword). Make sure you are using the latest version of the ODBC Driver (version 17). More info https://docs.microsoft.com/en-us/sql/connect/odbc/using-azure-active-directory?view=sql-server-2017

The problem here is that my customer has federated their on-premises Active Directory (AD) with Azure AD through ADFS and this method of authentication is not yet supported in Linux as this is done through an ADAL DLL that is only available for Windows. Sounds like a bunch of work to port the whole code that does this authentication, so we might not see in a near future the Linux ODBC driver supporting Azure AD Federated users. Microsoft has created ADAL libraries in other languages as well and I'm using the Python one in this example (https://github.com/AzureAD/azure-activedirectory-library-for-python).
To start I'm assuming you already have a SQL Database created in Azure, but if you don't click here to learn how to do it.

## Service Principals
Service Principals in Azure AD work just as SPN in an on-premises AD. To create one, you must first create an Application in your Azure AD. You can use this piece of code:
```
#Azure CLI 2.0
az ad sp create-for-rbac --name MyApp --password SomeStrongPassword
#PowerShell
#get the application we want a service principal for
$app = Get-AzureRmADApplication -DisplayNameStartWith MyApp
New-AzureRmADServicePrincipal -ApplicationId $app.ApplicationId -DisplayName MyApp -Password SomeStrongPassword
```
## Granting Access to the Database
First you need to set an AD Admin to your Azure SQL Logical Server. Follow these steps: https://docs.microsoft.com/en-us/azure/sql-database/sql-database-aad-authentication-configure#provision-an-azure-active-directory-administrator-for-your-azure-sql-database-server
After you set this up, log in your Database from SSMS or other tool that you use to manage your database and execute those two statements:
```
CREATE USER [MyApp] FROM EXTERNAL PROVIDER
EXEC sp_addrolemember 'db_owner', 'MyApp'
```
## Retrieving an AccessToken from Azure AD
First things first, don't forget to install and import adal and pyodbc. Now we should define the authority_url, which is composed by the AuthorityHostUrl (for Azure identities it should be "https://login.microsoftonline.com") + your tenantID. (find out your tenantID)
```
#define the authority URL and your tenant ID
##In Azure
###authorityHostUrl = "https://login.microsoftonline.com" 
authority_url = ('authorityHostUrl' + '/' +
                 'tenantID')
```                 
You also need to define the AuthorizationContext:
```
context = adal.AuthenticationContext(
    authority_url, api_version=None
    )
```
And now the tricky part, using the right function and parameters to acquire a token for a specific resource, in our case Azure SQL Database. The resource_uri for Azure SQL Database is https://database.windows.net/ (don't forget the trailing slash in the end, it won't work if you forget). ClientID is the application ID of the application you created in the beginning and to get the clientSecret log in to the portal, go to the Active Directory resource and App Registration. Click on keys and create a key to your app, this will be your clientSecret.
```
token = context.acquire_token_with_client_credentials(
    "https://database.windows.net/",
    'clientId',
    'clientSecret')
```
Now to use the acquired token, you also need to do some tricks. Python doesn't recognize some SQL types that we need to use before opening a connection using attributes. So first we need to define what the token means. SQL_COPT_SS_ACCESS_TOKEN is 1256; it's specific to msodbcsql driver so pyodbc does not have it defined, and likely will not. Then we need to translate the token to a data format that SQL understands. 
To give an end-to-end description, if the JSON response containing the token from the OAuth server looks like the bytes "eyJ0eXAiOi..." (in hex 65 79 4A 30 65 58 41 69 4F 69...) then the structure passed to the driver needs to have a 0 byte inserted after every token byte, e.g. 65 00 79 00 4A 00 30 00 65 00 58 00 41 00 69 00 4F 00 69 00... And this is what we are doing here, I'm using Python3 here. If you are using Python2 the approach might be different, but the idea is the same. Have in mind that you only need the accessToken itself (part of the JSON response) not the whole bearerToken.
```
SQL_COPT_SS_ACCESS_TOKEN = 1256 
connString = "Driver={ODBC Driver 17 for SQL Server};SERVER=yoursqlserver.database.windows.net;DATABASE=yourdatabase"
tokenb = bytes(token["accessToken"], "UTF-8")
exptoken = b''.join(b.to_bytes(2,'little') for b in bytes(token["accessToken"],'utf-8'))
tokenstruct = struct.pack("=i", len(exptoken)) + exptoken;
```
The connection String should look like this:
```
conn = pyodbc.connect(connString, attrs_before = { SQL_COPT_SS_ACCESS_TOKEN:tokenstruct});

#sample query using AdventureWorks
cursor = conn.cursor()
cursor.execute("SELECT TOP 20 pc.Name as CategoryName, p.name as ProductName FROM [SalesLT].[ProductCategory] pc JOIN [SalesLT].[Product] p ON pc.productcategoryid = p.productcategoryid")
row = cursor.fetchone()
while row:
    print (str(row[0]) + " " + str(row[1]))
    row = cursor.fetchone()
```
I hope this helps someone looking for help with this matter. Solution now in the official ADAL Wiki Page: https://github.com/AzureAD/azure-activedirectory-library-for-python/wiki/Connect-to-Azure-SQL-Database

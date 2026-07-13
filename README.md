# Proxy Server written in python using the flask framework

## Steps to run the proxy server in your local system

1. Install Python 3
2. Clone the git
3. Run the following commands:
```
pip install -r requirements.txt
python proxy.py
```

Server will be started with the default port '9099'. You can change the port in the code in proxy.py file.


## Configuration for the proxy server

Go to the "config" folder.

### Format for the app-config.json to add a new application endpoint:
```
{
	"<application_name>": {
		"fullyQualifiedApplicationName": "<any_fqan>",
		"applicationURL": "<application_host>",
		"landscapeHost": "<landscape_host>",
		"clientId": "<clientid_of_application>",
		"clientSecret": "<clientsecret_of_application>",
		"endPoints": {
			"<any_service_name>": {
				"serviceName": "<any_service_name>",
				"serviceURI": "<relative_service_uri>",
				"tenants": {
					"<subdomain_id>": {
						"tenantId": "<tenant_id_guid>",
						"subdomainId": "<subdomain_id>"
					}
				}
			}
		}
	}
}
```



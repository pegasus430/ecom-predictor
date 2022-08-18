# Edit & Maintain Retail Servers

## Overview

The purpose of this ticket is to create a RestAPI responsible for editing server credentials. We will be setting up server credentials which will log into various sites. 

We need an API for setting up those credentials when save is clicked in the UI, for storing the different server configurations, and for displaying which ones have been set up. This will also allow us to have one centralized location for displaying all servers that have been set up.

## Link to detailed specs

[Detailed Specs](https://www.dropbox.com/s/o1vb2ldoqlf4al9/Content%20Syndication%20v2.pdf?dl=0)

## Tickets

UI Tickets
 
* CON-26744 - Clean up Retailer Credentials UI
* CON-26747 - UI New System section called "Retail Servers", System>>Retail Servers to display Retail Server information

API Ticket

* CON-26753 API enables/modifies/disables servers

## Workflow
* User edits login credentials and information (CON-26744)
* User clicks save button which calls Retail Servers API, which enables/updates existing calls to retail servers (CON-26744 calls CON-26753)
* User clicks into System>>Retail Servers to see which servers have been enabled, and gets server information (CON-26747)
* Clicking into System>>Retail Servers calls API to populate iframe (CON-26747 calls CON-26753)
* User is able to disable server calls form this location (CON-26747)

## System>>Retail Servers
New System section called "Retail Servers", System>>Retail Servers  
3) and 4) will ideally be accomplished just by making the one call to the API. The API should actually display all content and buttons in iframe.

1) There should be an iframe.

2) Opening page initials API call to populate iframe with information from retail-servers.contentanalyticsinc.com.

The call to the server will be something like, populateRetailServers(server). This will call the API and specify which server the API should fetch retail server data for.

3) Returned information will be displayed in a table format:  
ID | Server Name | Site | Frequency | On/Off | Last Update | Status | Actions |

* Server Name = Section Header from Retailer Credentials
* Site = Retailer
* Frequency = daily/weekly/etc.
* On/Off = Is the server turned on or off
* Last update = The last time a request to the server was made
* Status = Any error info from the last time a request was made to the server
* Actions = "enable/disable" buttons

4) Under "actions" column, have enable/disable button
Clicking either of these buttons will call API to enable/disable this server call.

## API
Create an API which will enable/update these servers from Settings>>Retailer Credentials. Whenever a server is created, it will need to return an ID which is saved, and can be referenced by update server.

### 1) CreateServer(key, site, type, email, password, username, additional_emails, frequency, report_name)

* key is secret or private key used for the API to prevent unauthorized access. not sure which one needs to be used. 
* site is, e.g.: {amazon.com, target.com, walmart.com}
* type is one of Sales, Inventory, Traffic, Syndication
* \*email = email address 
* \*password = password (Need to figure out where this gets unencrypted to build the server)
* \*username = username (Need to figure out where this gets unencrypted to build the server)
* \*additional_emails = an array of email addresses
* \*period is one of {History, Daily, Weekly}
* \*report_name is a text field entry for the Report Name  
\*means that field is optional

### 2) UpdateServer(ID, key, site, type, email, password, username, additional_emails)

* ID is used to know which existing server to update

### 3) getServerInfo(ID)

* Return server information for the server with that ID

### 4) enableServer(ID)

### 5) disableServer(ID)

### 6) populateRetailServers(server)

API should return useful error info if server fails to be created or updated for any reason (invalid email, invalid fields for "type", etc.)
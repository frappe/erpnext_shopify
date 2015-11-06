Install ERPNext's, ERPNext-Shopify Connector app from Installer 
<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker1.1.png">

Now, you can connect your shopify account to ERPNext account by two ways.

 - Connect via Public App
 - Connect via Private APP


#### Connect via Public App
Get(install) ERPNext Connector from Shopify App Store, <a href="https://apps.shopify.com/erpnext-connector-1"> ERPNext Connector </a>

After clicking on Get button, it will redirect you to **ERPNext Shopify Connector** Page. Fillup correct data and click on Submit button. 
<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker1.2.png">

After Submitting a form, it will redirect to Permission Page. It will ask for permissions.

 - Modify Products, variants and collections
 - Modify Customer details and customer groups
 - Modify Orders, transactions and fulfillments

<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker1.3.png">

After installing Connector, login to your ERPNext Account and setup Shopify Settings page.

#### Connect via Private APP

From Shopify admin desk, create private app , APP > Private App

<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker2.1.png">

Each App has its own API key and Password. 

<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker2.2.png">

Pick up API key and Password, place them inside ERPNext Shopify Settings page.

<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker2.3.png">


#### Setup Shopify Settings

> Setup > Integrations > Shopify Settings

<img class="screenshot" src="{{ docs_base_url }}/assets/img/broker1.4.png">

#### Sync Data
There are two options to sync data.

Click on Sync Shopify button on Shopify Settings page for instant sync. 

<img class="screenshot" src="{{ docs_base_url }}/assets/img/sync.png">

By default, scheduler which will sync data on hourly basis.

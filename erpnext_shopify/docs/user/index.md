# ERPNext Shopify Connector

This app synchronizes the following data between your Shopify and ERPNext accounts

1. Products
1. Customers
1. Orders, payments and order fulfillment from Shopify into ERPNext

---

## Setup

1. [Install]({{ docs_base_url }}/index.html#install) ERPNext Shopify app in your ERPNext site
1. Connect your Shopify account to ERPNext
	1. Connect via the Public ERPNext App in Shopify's App Store (recommended)
	1. Connect by creating a Private App
	
#### Connect via the Public ERPNext App

1. Login to your Shopify account and install [ERPNext app](https://apps.shopify.com/erpnext-connector-1) from the Shopify App Store
1. On installing the app, you will be redirected to **ERPNext Shopify Connector** page where you will need to fill in your ERPNext credentials and then click on Submit    
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/broker1.2.png">    
1. Next, you will be taken to the Permissions page, where you will be asked to allow ERPNext to:
    - Modify Products, variants and collections
    - Modify Customer details and customer groups
    - Modify Orders, transactions and fulfillments    
	<img class="screenshot" src="{{ docs_base_url }}/assets/img/permission.png">
1. Next, login to your ERPNext site, go to Setup > Integrations > Shopify Settings and modify the connector's configuration

#### Connect by creating a Private App

1. From within your Shopify account, go to Apps > Private Apps > Create a Private App
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/shopify-private-apps-page.png">
1. Give it a title and save the app. Shopify will generate a unique API Key and Password for this app
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/shopify-new-private-app.png">
1. Login to your ERPNext site, then navigate to Setup > Integrations > Shopify Settings
1. Select the App Type as "Private", specify your Shopify account's URL, copy the private app's API Key and Password into the form and save the settings
    <img class="screenshot" src="{{ docs_base_url }}/assets/img/erpnext-config-for-private-app.png">

---

## Shopify Settings

> Setup > Integrations > Shopify Settings

1. Specify Price List and Warehouse to be used in the transactions
1. Specify which Cash/Bank Account to use for recording payments
1. Map Shopify Taxes and Shipping to ERPNext Accounts
1. Mention the Series to be used by the transactions created during sync

<img class="screenshot" src="{{ docs_base_url }}/assets/img/setup-shopify-settings.png">

---

## Synchronization

The connector app synchronizes data between Shopify and ERPNext automatically, every hour. However, you can initiate a manual sync by going to Setup > Integrations > Shopify Settings and clicking on **Sync Shopify**

<img class="screenshot" src="{{ docs_base_url }}/assets/img/sync.png">


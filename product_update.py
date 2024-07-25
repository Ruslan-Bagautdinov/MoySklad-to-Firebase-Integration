import json
import os
import traceback

import requests
from firebase_admin import db
from loguru import logger

from category_update import Category
from config import BASE_DIR, API_TOKEN


class ProductManager:
    def __init__(self, access_token, firebase_app):
        """
        Initialize the ProductManager with access token and Firebase app.

        Args:
            access_token (str): The access token for MoySklad API.
            firebase_app (App): The Firebase app instance.
        """
        self.access_token = access_token
        self.firebase_app = firebase_app
        self.ref = db.reference('/', app=self.firebase_app)
        self.MOYSKLAD_API_URL = "https://api.moysklad.ru/api/remap/1.2"
        self.all_products = []
        self.category_hierarchy = {}

    def fetch_categories(self):
        """
        Fetch and process categories from MoySklad.
        """
        category_manager = Category(self.access_token, self.firebase_app)
        category_manager.run()
        self.category_hierarchy = category_manager.process_categories()

    def fetch_products_from_moysklad(self):
        """
        Fetch products from MoySklad API.
        """
        url = f"{self.MOYSKLAD_API_URL}/entity/product"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json"
        }
        params = {
            "limit": 1000,
            "offset": 0
        }
        self.all_products = []
        while True:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                products = data.get("rows", [])
                for product in products:
                    if not all(key in product for key in
                               ["id", "name", "productFolder", "salePrices", "attributes", "images"]):
                        logger.error(f"Invalid product data: {product}")
                        continue
                    self.all_products.append(product)
                if len(products) < params["limit"]:
                    break
                else:
                    params["offset"] += params["limit"]
            else:
                logger.error(f"Error fetching products: {response.status_code}")
                logger.error(f"Response: {response.text}")
                break
        logger.info(f"Fetched {len(self.all_products)} products from Moysklad")

    def fetch_stock_from_moysklad(self):
        """
        Fetch stock data from MoySklad API.

        Returns:
            dict: A dictionary containing stock data.
        """
        url = f"{self.MOYSKLAD_API_URL}/report/stock/all/current"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            stock_data = {item["assortmentId"]: item["stock"] for item in data if
                          "assortmentId" in item and "stock" in item}
            return stock_data
        else:
            logger.error(f"Error fetching stock: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return {}

    def update_firebase_products(self, products, stock_data):
        """
        Update products in Firebase Realtime Database.

        Args:
            products (list): List of products to update.
            stock_data (dict): Dictionary containing stock data.
        """
        products_ref = self.ref.child("Products")
        updated_count = 0
        firebase_product_ids = set()

        firebase_products = products_ref.get()
        if firebase_products:
            for product_id, product_data in firebase_products.items():
                firebase_product_ids.add(product_id)

        moysklad_product_ids = set()

        for product in products:
            product_id = product["id"]
            moysklad_product_ids.add(product_id)
            firebase_product = products_ref.child(product_id).get()

            if "supplier" in product and product["supplier"] is not None:
                supplier_id = product["supplier"]["meta"]["href"].split("/")[-1]
            else:
                supplier_id = None

            subcategory_id = product["productFolder"]["meta"]["href"].split("/")[-1]
            category_id = self.find_category_id(subcategory_id)

            price = product["salePrices"][0]["value"] / 100.0

            existing_img_link = firebase_product.get("img") if firebase_product else None
            if existing_img_link and existing_img_link.startswith("https://imagedelivery.net"):
                img_link = existing_img_link
            else:
                img_link = product["images"]["meta"]["href"]

            product_data = {
                "brand_id": None,
                "category_id": category_id,
                "count": stock_data.get(product_id, 0),
                "description": product["description"],
                "header": product["name"],
                "id": product_id,
                "img": img_link,
                "popularity": product["attributes"][0]["value"],
                "price": price,
                "subcategory_id": subcategory_id,
                "suplier_id": supplier_id
            }

            if firebase_product:
                for key, value in product_data.items():
                    if firebase_product.get(key) != value:
                        if value is None:
                            logger.error(
                                f"Value is None for product_id: {product_id}, product name: {product['name']}, key: {key}")
                        else:
                            products_ref.child(product_id).child(key).set(value)
                            logger.info(f"Updated product '{product['name']}' key '{key}' in Firebase")
                            updated_count += 1
            else:
                for key, value in product_data.items():
                    if value is None:
                        logger.error(
                            f"Value is None for product_id: {product_id}, product name: {product['name']}, key: {key}")
                    else:
                        products_ref.child(product_id).child(key).set(value)
                        logger.info(f"Added new product '{product['name']}' in Firebase")
                        updated_count += 1

        products_to_delete = firebase_product_ids - moysklad_product_ids
        for product_id in products_to_delete:
            products_ref.child(product_id).delete()
            logger.info(f"Deleted product '{product_id}' from Firebase")

        logger.info(f"Updated {updated_count} products in Firebase")

    def find_category_id(self, subcategory_id):
        """
        Find the category ID for a given subcategory ID.

        Args:
            subcategory_id (str): The subcategory ID.

        Returns:
            str: The category ID.
        """
        for category_name, category_info in self.category_hierarchy.items():
            for subcategory in category_info.get('subcategories', []):
                if subcategory['id'] == subcategory_id:
                    return category_info['id']
        logger.error(f"Category ID not found for subcategory ID: {subcategory_id}")
        return None

    def save_products_to_json(self):
        """
        Save products to a JSON file for logging purposes.
        """
        if not os.path.exists(os.path.join(BASE_DIR, "json_logs")):
            os.makedirs(os.path.join(BASE_DIR, "json_logs"))
        with open(os.path.join(BASE_DIR, "json_logs", "products.json"), "w", encoding="utf-8") as f:
            json.dump(self.all_products, f, ensure_ascii=False, indent=4)
        logger.info("Products saved to products.json")

    def fetch_firebase_products(self):
        """
        Fetch products from Firebase Realtime Database.

        Returns:
            dict: A dictionary containing products.
        """
        firebase_products = self.ref.child('Products').get()
        if firebase_products:
            return firebase_products
        else:
            logger.warning("No products found in Firebase")
            return {}

    def log_firebase_products(self, firebase_products):
        """
        Log the products fetched from Firebase.

        Args:
            firebase_products (dict): Dictionary containing products.
        """
        logger.info("Firebase products:")
        logger.debug(f"Firebase Products: {json.dumps(firebase_products, ensure_ascii=False, indent=4)}")

    def create_product_image_list(self):
        """
        Create a list of product image links.

        Returns:
            list: A list of dictionaries containing product IDs and image links.
        """
        product_image_list = []
        for product in self.all_products:
            product_id = product["id"]
            image_link = f"https://api.moysklad.ru/api/remap/1.2/entity/product/{product_id}/images"
            product_image_list.append({
                "product_id": product_id,
                "image_link": image_link
            })

        logger.info("Product images list created")
        return product_image_list

    def send_product_images_to_fastapi(self, product_image_list):
        """
        Send the product image list to a FastAPI endpoint for processing.

        Args:
            product_image_list (list): List of dictionaries containing product IDs and image links.
        """
        url = "http://185.244.218.194:8015/product-images"
        headers = {
            "Authorization": API_TOKEN,
            "Content-Type": "application/json"
        }
        response = requests.post(url, headers=headers, json=product_image_list)
        if response.status_code == 200 or response.status_code == 204:
            logger.info("Product images successfully sent to FastAPI handler")
        else:
            logger.error(f"Failed to send product images to FastAPI handler: {response.status_code}")
            logger.error(f"Response: {response.text}")

    def fetch_firebase_database(self):
        """
        Fetch the entire Firebase database for logging purposes.
        """
        firebase_data = self.ref.get()
        if firebase_data:
            logger.info("Fetched entire Firebase database:")
            logger.debug(f"Firebase Database: {json.dumps(firebase_data, ensure_ascii=False, indent=4)}")
        else:
            logger.warning("No data found in Firebase")

    def run(self):
        """
        Run the product update process.
        """
        try:
            self.fetch_firebase_database()
            self.fetch_categories()
            self.fetch_products_from_moysklad()
            stock_data = self.fetch_stock_from_moysklad()
            self.update_firebase_products(self.all_products, stock_data)
            self.save_products_to_json()
            firebase_products = self.fetch_firebase_products()
            self.log_firebase_products(firebase_products)
            product_image_list = self.create_product_image_list()

            product_image_list_json = json.dumps(product_image_list, ensure_ascii=False)

            logger.info(f"IMAGE LIST: {product_image_list_json}")
            self.send_product_images_to_fastapi(product_image_list)
            logger.info("All products updated successfully")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Current state of all_products: {self.all_products}")
            logger.error(f"Current state of category_hierarchy: {self.category_hierarchy}")
            logger.error(f"Current state of stock_data: {stock_data}")
            logger.error(f"Current state of firebase_products: {firebase_products}")
            logger.error(f"Current state of product_image_list: {product_image_list}")


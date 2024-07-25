import json
import os

import requests
from firebase_admin import db
from loguru import logger

from config import BASE_DIR


class Category:
    def __init__(self, access_token, firebase_app):
        """
        Initialize the Category manager with access token and Firebase app.

        Args:
            access_token (str): The access token for MoySklad API.
            firebase_app (App): The Firebase app instance.
        """
        self.access_token = access_token
        self.firebase_app = firebase_app
        self.ref = db.reference('/', app=self.firebase_app)
        self.base_url = "https://api.moysklad.ru/api/remap/1.2/entity/productfolder"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json"
        }
        self.params = {"limit": 1000, "offset": 0}
        self.all_categories = []

    def fetch_categories(self):
        """
        Fetch categories from MoySklad API.
        """
        while True:
            response = requests.get(self.base_url, headers=self.headers, params=self.params)
            if response.status_code == 200:
                data = response.json()
                categories = data.get("rows", [])
                self.all_categories.extend(categories)
                if len(categories) < self.params["limit"]:
                    break
                else:
                    self.params["offset"] += self.params["limit"]
            else:
                logger.error(f"Error fetching categories. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                break
        logger.info(f"Total categories fetched from Moysklad: {len(self.all_categories)}")

    def process_categories(self):
        """
        Process the fetched categories.

        Returns:
            dict: A dictionary containing the category structure.
        """
        category_structure = {}
        sorted_categories = sorted(self.all_categories, key=lambda x: x['pathName'] != "")
        for category in sorted_categories:
            category_id = category['id']
            category_name = category['name']
            path_name = category['pathName']
            description = category.get('description', '')
            if path_name == "":
                category_structure[category_name] = {'id': category_id, 'subcategories': []}
            else:
                if path_name in category_structure:
                    category_structure[path_name]['subcategories'].append(
                        {'id': category_id, 'name': category_name, 'description': description})
                else:
                    logger.warning(f"Parent category {path_name} not found in the structure")
        logger.info("Processed category structure:")
        logger.debug(f"Category Structure: {json.dumps(category_structure, ensure_ascii=False, indent=4)}")
        return category_structure

    def update_firebase(self, category_structure):
        """
        Update categories in Firebase Realtime Database.

        Args:
            category_structure (dict): Dictionary containing the category structure.
        """
        firebase_categories = self.ref.child('Category').get()
        firebase_categories_dict = {}
        if firebase_categories:
            for category_id, category_data in firebase_categories.items():
                firebase_categories_dict[category_id] = category_data

        for category_name, category_info in category_structure.items():
            category_id = category_info['id']
            subcategories = category_info['subcategories']
            self._update_category(category_id, category_name, subcategories, firebase_categories_dict)

        for firebase_category_id in firebase_categories_dict:
            if firebase_category_id not in [cat['id'] for cat in self.all_categories]:
                self.ref.child(f'Category/{firebase_category_id}').delete()
                logger.info(f"Deleted category '{firebase_category_id}' from Firebase")

        logger.info("Categories synchronized with Firebase")

    def _update_category(self, category_id, category_name, subcategories, firebase_categories_dict):
        """
        Update a category in Firebase Realtime Database.

        Args:
            category_id (str): The category ID.
            category_name (str): The category name.
            subcategories (list): List of subcategories.
            firebase_categories_dict (dict): Dictionary containing Firebase categories.
        """
        if category_id in firebase_categories_dict:
            if firebase_categories_dict[category_id]['name'] != category_name:
                self.ref.child(f'Category/{category_id}/name').set(category_name)
                logger.info(f"Updated category name for '{category_name}'")
        else:
            self.ref.child(f'Category/{category_id}').set({
                'id': category_id,
                'name': category_name,
                'subcategory': {}
            })
            logger.info(f"Added new category '{category_name}'")
            firebase_categories_dict[category_id] = {
                'id': category_id,
                'name': category_name,
                'subcategory': {}
            }

        for subcategory in subcategories:
            subcategory_id = subcategory['id']
            subcategory_name = subcategory['name']
            subcategory_description = subcategory.get('description', '')
            self._update_subcategory(category_id, subcategory_id, subcategory_name, subcategory_description,
                                     firebase_categories_dict)

    def _update_subcategory(self, category_id, subcategory_id, subcategory_name, subcategory_description,
                            firebase_categories_dict):
        """
        Update a subcategory in Firebase Realtime Database.

        Args:
            category_id (str): The category ID.
            subcategory_id (str): The subcategory ID.
            subcategory_name (str): The subcategory name.
            subcategory_description (str): The subcategory description.
            firebase_categories_dict (dict): Dictionary containing Firebase categories.
        """
        if subcategory_id in firebase_categories_dict[category_id].get('subcategory', {}):
            if firebase_categories_dict[category_id]['subcategory'][subcategory_id]['header'] != subcategory_name:
                self.ref.child(f'Category/{category_id}/subcategory/{subcategory_id}/header').set(subcategory_name)
                logger.info(f"Updated subcategory name for '{subcategory_name}' under category '{category_id}'")
            if firebase_categories_dict[category_id]['subcategory'][subcategory_id]['img'] != subcategory_description:
                self.ref.child(f'Category/{category_id}/subcategory/{subcategory_id}/img').set(subcategory_description)
                logger.info(f"Updated subcategory description for '{subcategory_name}' under category '{category_id}'")
        else:
            self.ref.child(f'Category/{category_id}/subcategory/{subcategory_id}').set({
                'header': subcategory_name,
                'id': subcategory_id,
                'img': subcategory_description
            })
            logger.info(f"Added new subcategory '{subcategory_name}' under category '{category_id}'")
            if 'subcategory' not in firebase_categories_dict[category_id]:
                firebase_categories_dict[category_id]['subcategory'] = {}
            firebase_categories_dict[category_id]['subcategory'][subcategory_id] = {
                'header': subcategory_name,
                'id': subcategory_id,
                'img': subcategory_description
            }

    def save_categories_to_json(self):
        """
        Save categories to a JSON file for logging purposes.
        """
        with open(os.path.join(BASE_DIR, "json_logs", "categories.json"), "w", encoding="utf-8") as f:
            json.dump(self.all_categories, f, ensure_ascii=False, indent=4)
        logger.info("Categories saved to categories.json")

    def fetch_firebase_categories(self):
        """
        Fetch categories from Firebase Realtime Database.

        Returns:
            dict: A dictionary containing categories.
        """
        firebase_categories = self.ref.child('Category').get()
        if firebase_categories:
            return firebase_categories
        else:
            logger.warning("No categories found in Firebase")
            return {}

    def log_firebase_categories(self, firebase_categories):
        """
        Log the categories fetched from Firebase.

        Args:
            firebase_categories (dict): Dictionary containing categories.
        """
        logger.info("Firebase categories:")
        logger.debug(f"Firebase Categories: {json.dumps(firebase_categories, ensure_ascii=False, indent=4)}")

    def run(self):
        """
        Run the category update process.
        """
        self.fetch_categories()
        category_structure = self.process_categories()
        self.update_firebase(category_structure)
        self.save_categories_to_json()
        firebase_categories = self.fetch_firebase_categories()
        self.log_firebase_categories(firebase_categories)


import json
import os

import requests
from firebase_admin import db
from loguru import logger

from config import BASE_DIR


class Counterparty:
    def __init__(self, access_token, firebase_app):
        """
        Initialize the Counterparty manager with access token and Firebase app.

        Args:
            access_token (str): The access token for MoySklad API.
            firebase_app (App): The Firebase app instance.
        """
        self.access_token = access_token
        self.firebase_app = firebase_app
        self.ref = db.reference('/', app=self.firebase_app)
        self.base_url = "https://api.moysklad.ru/api/remap/1.2/entity/counterparty"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json"
        }
        self.params = {"limit": 1000, "offset": 0}
        self.all_counterparties = []

    def fetch_counterparties(self):
        """
        Fetch counterparties from MoySklad API.
        """
        logger.info("Starting to fetch counterparties from Moysklad...")
        while True:
            response = requests.get(self.base_url, headers=self.headers, params=self.params)
            if response.status_code == 200:
                data = response.json()
                counterparties = data.get("rows", [])
                self.all_counterparties.extend(counterparties)
                logger.info(f"Fetched {len(counterparties)} counterparties from Moysklad.")
                if len(counterparties) < self.params["limit"]:
                    break
                else:
                    self.params["offset"] += self.params["limit"]
            else:
                logger.error(f"Error fetching counterparties. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                break
        logger.info(f"Total counterparties fetched from Moysklad: {len(self.all_counterparties)}")

    def process_counterparties(self):
        """
        Process the fetched counterparties.

        Returns:
            dict: A dictionary containing processed counterparties.
        """
        logger.info("Processing counterparties...")
        processed_counterparties = {}
        for counterparty in self.all_counterparties:
            counterparty_id = counterparty['id']
            counterparty_name = counterparty['name']
            phone = counterparty.get('phone', '')
            attributes = counterparty.get('attributes', [])
            delivery_price = next((attr['value'] for attr in attributes if attr['name'] == 'Стоимость доставки'), None)
            delivery_time_days = next((attr['value'] for attr in attributes if attr['name'] == 'Срок доставки'), None)
            description = next((attr['value'] for attr in attributes if attr['name'] == 'Описание поставщика'), '')
            logo_link = next((attr['value'] for attr in attributes if attr['name'] == 'Ссылка на логотип'), '')
            processed_counterparties[counterparty_id] = {
                "id": counterparty_id,
                "name": counterparty_name,
                "phone": phone,
                "delivery_price": delivery_price,
                "delivery_time_days": delivery_time_days,
                "description": description,
                "logo_link": logo_link
            }
        logger.info("Processed counterparties structure:")
        logger.debug(f"Counterparties Structure: {json.dumps(processed_counterparties, ensure_ascii=False, indent=4)}")
        return processed_counterparties

    def update_firebase(self, processed_counterparties):
        """
        Update counterparties in Firebase Realtime Database.

        Args:
            processed_counterparties (dict): Dictionary containing processed counterparties.
        """
        logger.info("Fetching counterparties from Firebase...")
        firebase_counterparties = self.ref.child('Supliers').get()
        firebase_counterparties_dict = {}
        if firebase_counterparties:
            for counterparty_id, counterparty_data in firebase_counterparties.items():
                firebase_counterparties_dict[counterparty_id] = counterparty_data
        logger.info(
            f"Total counterparties fetched from Firebase: {len(firebase_counterparties) if firebase_counterparties else 0}")
        logger.debug(
            f"Counterparties from Firebase: {json.dumps(firebase_counterparties, ensure_ascii=False, indent=4)}")
        logger.info("Comparing and updating Firebase counterparties...")
        for counterparty_id, counterparty_info in processed_counterparties.items():
            if counterparty_id in firebase_counterparties_dict:
                if firebase_counterparties_dict[counterparty_id] != counterparty_info:
                    self.ref.child(f'Supliers/{counterparty_id}').set(counterparty_info)
                    logger.info(f"Updated counterparty '{counterparty_info['name']}'")
            else:
                self.ref.child(f'Supliers/{counterparty_id}').set(counterparty_info)
                logger.info(f"Added new counterparty '{counterparty_info['name']}'")
        logger.info("Deleting counterparties in Firebase if they don't exist in Moysklad...")
        for firebase_counterparty_id in firebase_counterparties_dict:
            if firebase_counterparty_id not in processed_counterparties:
                self.ref.child(f'Supliers/{firebase_counterparty_id}').delete()
                logger.info(f"Deleted counterparty '{firebase_counterparty_id}' from Firebase")
        logger.info("Counterparties synchronized with Firebase")

    def save_counterparties_to_json(self):
        """
        Save counterparties to a JSON file for logging purposes.
        """
        with open(os.path.join(BASE_DIR, "json_logs", "counterparties.json"), "w", encoding="utf-8") as f:
            json.dump(self.all_counterparties, f, ensure_ascii=False, indent=4)
        logger.info("Counterparties saved to counterparties.json")

    def fetch_firebase_supliers(self):
        """
        Fetch supliers from Firebase Realtime Database.

        Returns:
            dict: A dictionary containing supliers.
        """
        firebase_supliers = self.ref.child('Supliers').get()
        if firebase_supliers:
            return firebase_supliers
        else:
            logger.warning("No supliers found in Firebase")
            return {}

    def log_firebase_supliers(self, firebase_supliers):
        """
        Log the supliers fetched from Firebase.

        Args:
            firebase_supliers (dict): Dictionary containing supliers.
        """
        logger.info("Firebase supliers:")
        logger.debug(f"Firebase Supliers: {json.dumps(firebase_supliers, ensure_ascii=False, indent=4)}")

    def run(self):
        """
        Run the counterparty update process.
        """
        self.fetch_counterparties()
        processed_counterparties = self.process_counterparties()
        self.update_firebase(processed_counterparties)
        self.save_counterparties_to_json()
        firebase_supliers = self.fetch_firebase_supliers()
        self.log_firebase_supliers(firebase_supliers)


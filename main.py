import os
import time

from firebase_admin import credentials, initialize_app
from loguru import logger

from category_update import Category
from config import BASE_DIR, MY_SKLAD_ACCESS_TOKEN, FIREBASE_URL, FIREBASE_CRED, SLEEP
from counterparty_update import Counterparty
from product_update import ProductManager


def initialize_firebase(cred, database_url):
    """
    Initialize the Firebase app with the provided credentials and database URL.

    Args:
        cred (Credentials): The Firebase credentials.
        database_url (str): The URL of the Firebase Realtime Database.

    Returns:
        App: The initialized Firebase app.
    """
    try:
        app = initialize_app(cred, {'databaseURL': database_url})
        logger.info(f"Firebase initialized with URL: {database_url}")
        return app
    except ValueError as e:
        if "The default Firebase app already exists" in str(e):
            return initialize_app(cred, {'databaseURL': database_url}, name='secondary')
        else:
            raise e


def main():
    """
    Main function to run the data synchronization process between MoySklad and Firebase.
    """
    access_token = MY_SKLAD_ACCESS_TOKEN

    cred = credentials.Certificate(os.path.join(BASE_DIR, FIREBASE_CRED))
    logger.info(f"Credential: {cred}")

    firebase_url = FIREBASE_URL

    firebase_app = initialize_firebase(cred, firebase_url)
    logger.info(f"Firebase initialized with URL: {firebase_url}")

    while True:
        category_manager = Category(access_token, firebase_app)
        category_manager.run()

        counterparty_manager = Counterparty(access_token, firebase_app)
        counterparty_manager.run()

        product_manager = ProductManager(access_token, firebase_app)
        product_manager.run()
        product_image_list = product_manager.create_product_image_list()
        time.sleep(SLEEP)


if __name__ == "__main__":
    main()


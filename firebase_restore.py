import json
import os

import firebase_admin
from firebase_admin import credentials, db
from loguru import logger

from config import BASE_DIR, FIREBASE_URL, FIREBASE_CRED, BACKUP_FILE


class FirebaseRestorer:
    def __init__(self, service_account_key_path, backup_file_path):
        """
        Initialize the FirebaseRestorer with service account key path and backup file path.

        Args:
            service_account_key_path (str): Path to the Firebase service account key file.
            backup_file_path (str): Path to the backup JSON file.
        """
        self.service_account_key_path = service_account_key_path
        self.backup_file_path = backup_file_path
        self.firebase_app = None

    def initialize_firebase(self):
        """
        Initialize the Firebase app with the provided service account key and database URL.
        """
        cred = credentials.Certificate(self.service_account_key_path)
        database_url = FIREBASE_URL

        try:
            self.firebase_app = firebase_admin.initialize_app(cred, {'databaseURL': database_url})
            logger.info(f"Firebase initialized with URL: {database_url}")
        except ValueError as e:
            if "The default Firebase app already exists" in str(e):
                self.firebase_app = firebase_admin.initialize_app(cred, {'databaseURL': database_url}, name='secondary')
            else:
                raise e

    def load_backup_data(self):
        """
        Load the backup data from the JSON file.

        Returns:
            dict: The backup data loaded from the JSON file.
        """
        with open(self.backup_file_path, 'r') as file:
            data = json.load(file)
        logger.info("Backup data loaded from JSON file.")
        return data

    def restore_data(self, data):
        """
        Restore the data to Firebase Realtime Database.

        Args:
            data (dict): The data to be restored.
        """
        ref = db.reference('/', app=self.firebase_app)
        ref.set(data)
        logger.info("Data restored successfully to Firebase.")

    def run(self):
        """
        Run the Firebase restoration process.
        """
        self.initialize_firebase()
        data = self.load_backup_data()
        self.restore_data(data)


# Example usage
if __name__ == "__main__":
    backup_file_path = os.path.join(BASE_DIR, BACKUP_FILE)

    restorer = FirebaseRestorer(
        service_account_key_path=os.path.join(BASE_DIR, FIREBASE_CRED),
        backup_file_path=backup_file_path
    )
    restorer.run()


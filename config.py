import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MY_SKLAD_USERNAME = os.getenv('MY_SKLAD_USERNAME')
MY_SKLAD_PASSWORD = os.getenv('MY_SKLAD_PASSWORD')
MY_SKLAD_ACCESS_TOKEN = os.getenv('MY_SKLAD_ACCESS_TOKEN')

FIREBASE_URL = os.getenv('FIREBASE_URL')
FIREBASE_CRED = os.getenv('FIREBASE_CRED')
BACKUP_FILE = os.getenv('BACKUP_FILE')

SLEEP = int(os.getenv('SLEEP', 60))

API_TOKEN = os.getenv('API_TOKEN')


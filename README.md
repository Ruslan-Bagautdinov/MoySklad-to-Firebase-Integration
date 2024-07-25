# MoySklad to Firebase Integration

This project automates the process of fetching data from MoySklad (Products, Categories, and Counterparties) and updating them in Firebase Realtime Database. It also sends lists of image links from MoySklad to another API, which converts these links into images uploaded to CloudFlare Images. Additionally, it can restore Firebase from a backup JSON file.

## Features

- **Fetch Data from MoySklad**: Automatically fetches products, categories, and counterparties from MoySklad.
- **Update Firebase**: Updates the fetched data in Firebase Realtime Database.
- **Send Image Links**: Sends lists of product image links to another API for conversion and upload to CloudFlare Images.
- **Restore Firebase**: Restores Firebase from a backup JSON file.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/moySklad-to-firebase.git
   cd moySklad-to-firebase
   ```

2. **Set Up Environment Variables**:
Create a .env file in the root directory with the following content:

```dotenv
MY_SKLAD_USERNAME=your_moySklad_username
MY_SKLAD_PASSWORD=your_moySklad_password
MY_SKLAD_ACCESS_TOKEN=your_moySklad_access_token
FIREBASE_URL=your_firebase_database_url
FIREBASE_CRED=path_to_your_firebase_service_account_key.json
BACKUP_FILE=path_to_your_backup_file.json
SLEEP=60  # Interval in seconds between updates
API_TOKEN=your_api_token
```
3. **Install Dependencies**:

```bash
pip install -r requirements.txt
```

4. **Run the Application:**:

```bash
python main.py
```

## Usage

**Fetch and Update Data**: 
The application will automatically fetch data from MoySklad and update Firebase at the specified interval.

**Restore Firebase**: 
To restore Firebase from a backup, run:

```bash
python firebase_restore.py
```

## Logging
The application uses loguru for logging. Logs are saved in the console and can be configured to save to a file if needed.

## Contributing
Contributions are welcome! Please read the contributing guidelines before getting started.

## License
This project is not licensed.

## Contact
For any inquiries, please open an issue or contact the maintainers directly.


This `README.md` provides a comprehensive guide to setting up, installing, and using your project, along with information on logging, contributing, and licensing.


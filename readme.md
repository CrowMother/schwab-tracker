
# Schwab Tracker

A Python application designed to monitor and manage Charles Schwab account positions, facilitating order processing and providing webhook notifications.

## Features

- **Order Processing**: Automates the execution of buy and sell orders based on predefined criteria.
- **Database Management**: Utilizes SQLite to store order history and track open positions.
- **Webhook Notifications**: Sends real-time updates on order statuses and account changes.

## Requirements

- Python 3.8 or higher
- `requests` library
- `logging` module
- `Bot_App` library (ensure this is installed or accessible)

## Installation

1. **Clone the Repository**:

   ```bash
   git clone https://github.com/CrowMother/schwab-tracker.git
   ```


2. **Navigate to the Project Directory**:

   ```bash
   cd schwab-tracker
   ```


3. **Install Dependencies**:

   ```bash
   pip install -r requirements.txt
   ```


## Configuration

1. **Environment Variables**:

   Set the following environment variables for Schwab API authentication:

   - `SCHWAB_USERNAME`
   - `SCHWAB_PASSWORD`
   - `SCHWAB_TOTP_SECRET`

   These can be set in a `.env` file or directly in your environment.

2. **Database Setup**:

   The application uses an SQLite database (`DB.db`) to store order history and track positions. Ensure this file is accessible and has the appropriate read/write permissions.

## Usage

1. **Run the Application**:

   ```bash
   python main.py
   ```


   This will initiate the process of fetching account positions, processing orders, and sending webhook notifications as configured.

2. **Logging**:

   Logs are generated to provide insights into the application's operations. Ensure that the logging configuration in `main.py` is set up according to your preferences.

## Docker Deployment

1. **Build the Docker Image**:

   ```bash
   docker build -t schwab-tracker .
   ```


2. **Run the Docker Container**:

   ```bash
   docker run -d --name schwab-tracker schwab-tracker
   ```


   Ensure that environment variables are passed correctly and that the database file is mounted appropriately if you need persistent storage.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`feature-branch`).
3. Commit your changes.
4. Push to the branch.
5. Open a Pull Request.

## License

This project is licensed under the MIT License.

## Contact

For questions or suggestions, please open an issue in this repository.
``` 

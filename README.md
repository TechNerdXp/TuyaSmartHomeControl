# Tuya Smart Home Control

A Python application to control Tuya-enabled fans and lights using the Tuya IoT Platform.

## Prerequisites

- Python 3.7 or higher
- A Tuya IoT Platform account
- Tuya Smart Home devices (fans and lights)
- Your devices already set up in the Tuya Smart Home app

## Tuya Cloud Setup

### 1. Create Cloud Project

1. Login to [Tuya IoT Platform](https://iot.tuya.com/)
2. Navigate to "Cloud" → "Development"
3. Click "Create Cloud Project"
4. Fill in project details:
   - Name: Choose a meaningful name
   - Description: Optional description
   - Industry: Smart Home
   - Development Method: Smart Home
   - Data Center: Choose your region (e.g., Western Europe)

### 2. Configure Project Permissions

1. In your new project:
   - Go to "Project Overview"
   - Click "Project Settings"
2. Enable required services:
   - Authorization Management
   - Device Control
   - Device Status Notification
   - Device Management
3. Save your credentials:
   - Access ID (Client ID)
   - Access Secret (Client Secret)
   - Keep these safe for .env file

### 3. Link Your Devices

1. Install Tuya Smart app on your phone
2. Create account and add devices:
   - Download "Tuya Smart" or "Smart Life" app
   - Create an account
   - Add your devices following app instructions
   
2. Link app account to project:
   - In Tuya IoT Platform, go to "Cloud" → "Development"
   - Select your project
   - Click "Devices" tab
   - Click "Link Tuya App Account"
   - Scan QR code with your Tuya Smart app
   - Confirm the linking

3. Verify devices:
   - Your devices should appear in the device list
   - For each device, note:
     - Device ID
     - Category (fskg for fans, tdq for lights)
     - Device Name

### 4. Get Device Information

1. Click each device in the list to view:
   - Device ID (needed for config)
   - Category (needed for config)
   - Online status
   - Functions list

2. Save device details in config:
   - Use Device IDs in your devices.json
   - Match categories exactly (fskg, tdq)
   - Keep original device names for easy identification

## Setup Instructions

1. Install required packages:
```bash
pip install customtkinter tuya-connector-python python-dotenv Pillow requests
```

2. Get Your Device Information:

   a. Go to [Tuya IoT Platform](https://iot.tuya.com/)
   
   b. Create a new Cloud Project:
      - Navigate to Cloud -> Project
      - Click "Create" and follow the wizard
      - Select "Smart Home" scenario
      - Keep your Access ID and Access Secret

   c. Get Device Information:
      - Go to Cloud -> Devices
      - Click "Link Tuya App Account"
      - Scan QR code with your Tuya Smart Home app
      - Your devices will appear in the list
      - Click on each device to view its ID and other details

3. Configure the Application:

   a. Create `.env` file:
   ```
   TUYA_ACCESS_ID=your_access_id_here
   TUYA_ACCESS_KEY=your_access_secret_here
   TUYA_API_ENDPOINT=https://openapi.tuyaeu.com
   TUYA_CONFIG_FILE=config/devices.json
   ```

   b. Create `config/devices.json`:
   - Copy `config/devices.example.json`
   - Replace placeholder IDs with your actual device IDs
   - Keep the category codes:
     - `fskg` for fans
     - `tdq` for lights

## Device Categories

The application supports two types of devices:

- Fans (`fskg`):
  - ON/OFF control
  - Speed control (1-100%)
  - Status indication

- Lights (`tdq`):
  - ON/OFF control
  - Status indication

## Getting Complex Device Information

If you need detailed device information:

1. Use the Tuya IoT Platform Device Debug feature:
   - Go to Cloud -> Development -> Device Debug
   - Select your device
   - View all available functions and specs

2. Or use the API explorer:
   - Go to Cloud -> API Explorer
   - Use the `GET /v1.0/iot-03/devices/{device_id}/specification` endpoint
   - This will show all device capabilities and functions

3. Save the complex device information:
   - You can save detailed device specs in `devices_complex.json`
   - This is useful for reference when adding new features

## Running the Application

```bash
python main.py
```

The application will:
- Load your device configuration
- Connect to Tuya IoT Platform
- Show a control panel for all your devices
- Auto-detect system dark/light mode
- Cache device icons locally

## Building Windows Executable

### Prerequisites
```bash
pip install pyinstaller
```

### Build Steps

1. Prepare build environment:
   - Ensure all dependencies are installed
   - Check that config files are set up correctly
   - Make sure app.ico is present in assets folder

2. Run build script:
```bash
python build.py
```

3. Find executable:
   - Look in `dist` folder
   - File will be named `TuyaSmartControl.exe`
   - Contains all dependencies and configurations

4. Test the executable:
   - Run TuyaSmartControl.exe
   - Verify all features work
   - Check icon appears correctly

### Distribution

Share these files with users:
- TuyaSmartControl.exe
- config/devices.example.json (for setup reference)
- .env.example (for setup reference)

Users will need to:
1. Create their own .env file
2. Set up their devices.json
3. Run the executable

## Troubleshooting

1. Connection Issues:
   - Verify your Access ID and Access Key
   - Check if you're using the correct API endpoint
   - Ensure your project has the required permissions

2. Device Control Issues:
   - Verify device IDs in your config
   - Check if devices are online in the Tuya app
   - Ensure device categories are correct

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License

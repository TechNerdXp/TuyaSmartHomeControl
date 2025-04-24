import customtkinter as ctk
from tuya_connector import TuyaOpenAPI
import json
import darkdetect  # You'll need to: pip install darkdetect
from dotenv import load_dotenv
import os
from PIL import Image
import requests
from io import BytesIO
import hashlib
from pathlib import Path
import shutil
import sys
import pkg_resources
from datetime import datetime, timedelta

# Load and validate environment variables
load_dotenv()

def get_env_var(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return value

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# Get required environment variables
ACCESS_ID = get_env_var('TUYA_ACCESS_ID')
ACCESS_KEY = get_env_var('TUYA_ACCESS_KEY')
API_ENDPOINT = get_env_var('TUYA_API_ENDPOINT')
CONFIG_FILE = get_env_var('TUYA_CONFIG_FILE')

class CloudControl:
    def __init__(self):
        self.cloud_api = TuyaOpenAPI(API_ENDPOINT, ACCESS_ID, ACCESS_KEY)
        self.cloud_api.connect()
        
        devices_path = get_resource_path('devices.json')
        devices_example = get_resource_path('devices.example.json')
        
        if not os.path.exists(devices_path):
            if os.path.exists(devices_example):
                print("First run detected, creating devices.json from example...")
                shutil.copy(devices_example, devices_path)
                print("Please edit devices.json with your device IDs")
            else:
                raise FileNotFoundError(
                    "devices.json not found and no example file to copy from."
                )
        
        try:
            with open(devices_path, 'r') as f:
                self.devices = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in devices.json")

    def control(self, device_id, command, value):
        try:
            if command in ['switch_1', 'switch_fan']:
                status = self.cloud_api.get(f'/v1.0/iot-03/devices/{device_id}/status')
                if status['success']:
                    current = status['result'][0]['value']
                    value = not current

            cmd = {'commands': [{'code': command, 'value': value}]}
            return self.cloud_api.post(f'/v1.0/iot-03/devices/{device_id}/commands', cmd)
        except Exception as e:
            print(f"Control error: {str(e)}")
            return {'success': False}

    def get_device_status(self, device_id):
        try:
            status = self.cloud_api.get(f'/v1.0/iot-03/devices/{device_id}/status')
            if status['success']:
                return {item['code']: item['value'] for item in status['result']}
            return {}
        except Exception as e:
            print(f"Status fetch error: {str(e)}")
            return {}

    def get_all_statuses(self):
        statuses = {}
        for name, dev in self.devices.items():
            statuses[dev['id']] = self.get_device_status(dev['id'])
        return statuses

class CloudUI:
    def __init__(self):
        self.ctrl = CloudControl()
        self.asset_dir = Path(get_resource_path('assets'))
        
        # Setup window
        self.root = ctk.CTk()
        self.root.title("Smart Home Control")
        self.root.geometry("800x600")
        
        try:
            # Try to use the built-in CustomTkinter icon
            icon_path = pkg_resources.resource_filename('customtkinter', 'assets/icons/CustomTkinter_icon_3.png')
            if os.path.exists(icon_path):
                self.root.iconphoto(True, ctk.CTkImage(light_image=Image.open(icon_path), size=(64, 64))._light_image)
        except Exception as e:
            print(f"Warning: Could not load window icon: {e}")
        
        # Set appearance mode based on system
        system_mode = "dark" if darkdetect.isDark() else "light"
        ctk.set_appearance_mode(system_mode)
        ctk.set_default_color_theme("blue")
        
        # Main container with padding
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Main content frames
        content_frame = ctk.CTkFrame(self.main_frame)
        content_frame.pack(fill="both", expand=True)
        
        # Title
        title = ctk.CTkLabel(
            content_frame, 
            text="Smart Home Control", 
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.pack(pady=(0, 20))

        # Master Controls Section
        master_frame = ctk.CTkFrame(content_frame)
        master_frame.pack(fill="x", pady=(0, 20))
        
        master_title = ctk.CTkLabel(
            master_frame,
            text="Master Controls",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        master_title.pack(pady=(10, 5), padx=10)

        # Master toggle buttons
        master_buttons = ctk.CTkFrame(master_frame, fg_color="transparent")
        master_buttons.pack(fill="x", padx=10, pady=10)

        self.all_status = ctk.CTkLabel(master_buttons, text="All: Unknown")
        self.all_status.pack(side="left", padx=5)
        
        self.master_all = ctk.CTkButton(
            master_buttons,
            text="Toggle All",
            width=120,
            command=lambda: self.toggle_all_devices()
        )
        self.master_all.pack(side="left", padx=5)

        self.fans_status = ctk.CTkLabel(master_buttons, text="Fans: Unknown")
        self.fans_status.pack(side="left", padx=5)
        
        self.master_fans = ctk.CTkButton(
            master_buttons,
            text="Toggle Fans",
            width=120,
            command=lambda: self.toggle_category('fskg')
        )
        self.master_fans.pack(side="left", padx=5)

        self.lights_status = ctk.CTkLabel(master_buttons, text="Lights: Unknown")
        self.lights_status.pack(side="left", padx=5)
        
        self.master_lights = ctk.CTkButton(
            master_buttons,
            text="Toggle Lights",
            width=120,
            command=lambda: self.toggle_category('tdq')
        )
        self.master_lights.pack(side="left", padx=5)

        # Fans Section
        fans_frame = ctk.CTkFrame(content_frame)
        fans_frame.pack(fill="x", pady=(0, 20))
        
        fans_title = ctk.CTkLabel(
            fans_frame,
            text="Fans",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        fans_title.pack(pady=(10, 5), padx=10)
        
        # Lights Section
        lights_frame = ctk.CTkFrame(content_frame)
        lights_frame.pack(fill="x")
        
        lights_title = ctk.CTkLabel(
            lights_frame,
            text="Lights",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        lights_title.pack(pady=(10, 5), padx=10)
        
        self.lights_container = ctk.CTkFrame(lights_frame, fg_color="transparent")
        self.lights_container.pack(fill="x", padx=10, pady=(0, 10))
        
        # Store device references
        self.device_widgets = {}
        
        # Add devices
        for name, dev in self.ctrl.devices.items():
            if dev['category'] == 'fskg':
                self.add_fan(fans_frame, name, dev['id'])
            elif dev['category'] == 'tdq':
                self.add_light(self.lights_container, name, dev['id'])

        # Add expiration info at the bottom
        expiration_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        expiration_frame.pack(fill="x", pady=(10, 0))
        
        # Calculate API access period
        start_date = datetime.now()
        end_date = start_date + timedelta(days=180)
        
        expiration_text = (
            f"API Access Period: "
            f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )
        
        self.expiration_label = ctk.CTkLabel(
            expiration_frame,
            text=expiration_text,
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        self.expiration_label.pack(side="right", padx=10)

        # Initial status update
        self.update_all_statuses()

    def load_icon(self, url, size=(32, 32)):
        if not url:
            return None
        
        # Get local asset path from url or path
        if url.startswith('assets/'):
            image_path = Path(get_resource_path(url))
        else:
            filename = url.split('/')[-1]
            image_path = self.asset_dir / filename
        
        try:
            return ctk.CTkImage(
                light_image=Image.open(image_path),
                dark_image=Image.open(image_path),
                size=size
            )
        except Exception as e:
            print(f"Icon load error: {str(e)}")
            return None

    def add_fan(self, parent, name, dev_id):
        device_frame = ctk.CTkFrame(parent)
        device_frame.pack(fill="x", padx=10, pady=5)
        
        # Add icon if available
        icon_url = self.ctrl.devices[name].get('icon', '')
        icon_image = self.load_icon(icon_url)
        if icon_image:
            icon_label = ctk.CTkLabel(device_frame, image=icon_image, text="")
            icon_label.pack(side="left", padx=(0, 5))
        
        name_frame = ctk.CTkFrame(device_frame, fg_color="transparent")
        name_frame.pack(side="left", padx=10)
        
        name_label = ctk.CTkLabel(
            name_frame, 
            text=name,
            font=ctk.CTkFont(size=14)
        )
        name_label.pack(side="left", padx=(0, 5))
        
        status_label = ctk.CTkLabel(
            name_frame,
            text="OFF",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        status_label.pack(side="left")
        
        control_frame = ctk.CTkFrame(device_frame, fg_color="transparent")
        control_frame.pack(side="right", fill="x", expand=True, padx=10)
        
        toggle_btn = ctk.CTkButton(
            control_frame,
            text="Toggle",
            width=80,
            command=lambda: self.device_action(dev_id, 'switch_fan', True, toggle_btn)
        )
        toggle_btn.pack(side="left", padx=5)
        
        slider = ctk.CTkSlider(
            control_frame,
            from_=1,
            to=100,
            number_of_steps=99
        )
        slider.pack(side="left", fill="x", expand=True, padx=10)
        
        speed_label = ctk.CTkLabel(control_frame, text="50%")
        speed_label.pack(side="right", padx=5)
        
        slider.configure(command=lambda v: self.update_speed_label(speed_label, v))
        slider.bind(
            "<ButtonRelease-1>",
            lambda e: self.device_action(dev_id, 'fan_speed', int(slider.get()), toggle_btn)
        )

        self.device_widgets[dev_id] = {
            'button': toggle_btn,
            'status': status_label,
            'category': 'fskg',
            'slider': slider,
            'speed_label': speed_label
        }

        # Initialize with real status
        self.update_device_status(dev_id)

    def add_light(self, parent, name, dev_id):
        light_frame = ctk.CTkFrame(parent)
        light_frame.pack(side="left", padx=5, pady=5)
        
        # Load and add icon
        icon_url = self.ctrl.devices[name].get('icon', '')
        icon_image = self.load_icon(icon_url, size=(48, 48))
        if icon_image:
            icon_label = ctk.CTkLabel(light_frame, image=icon_image, text="")
            icon_label.pack(pady=5)
        
        status_label = ctk.CTkLabel(
            light_frame,
            text="OFF",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        status_label.pack(pady=(5, 0))
        
        btn = ctk.CTkButton(
            light_frame,
            text=name,
            width=120,
            height=40,
            command=lambda: self.device_action(dev_id, 'switch_1', True, btn)
        )
        btn.pack(padx=5, pady=5)

        self.device_widgets[dev_id] = {
            'button': btn,
            'status': status_label,
            'category': 'tdq'
        }

        # Initialize with real status
        self.update_device_status(dev_id)

    def update_speed_label(self, label, value):
        label.configure(text=f"{int(value)}%")

    def device_action(self, dev_id, cmd, value, widget):
        orig_fg = widget.cget("fg_color")
        orig_hover = widget.cget("hover_color")
        
        result = self.ctrl.control(dev_id, cmd, value)
        
        if result.get('success'):
            widget.configure(fg_color="green", hover_color="green")
            self.update_device_status(dev_id)
            self.update_all_statuses()
        else:
            widget.configure(fg_color="red", hover_color="red")
            
        self.root.after(1000, lambda: widget.configure(
            fg_color=orig_fg,
            hover_color=orig_hover
        ))

    def update_device_status(self, dev_id):
        status = self.ctrl.get_device_status(dev_id)
        if status:
            widget_info = self.device_widgets[dev_id]
            is_on = status.get('switch_1' if widget_info['category'] == 'tdq' else 'switch_fan', False)
            widget_info['status'].configure(
                text="ON" if is_on else "OFF",
                text_color="green" if is_on else "gray"
            )
            if widget_info['category'] == 'fskg' and 'fan_speed' in status:
                speed = status['fan_speed']
                if 'slider' in widget_info:
                    widget_info['slider'].set(speed)
                    self.update_speed_label(widget_info['speed_label'], speed)

    def update_all_statuses(self):
        statuses = self.ctrl.get_all_statuses()
        fan_states = []
        light_states = []
        
        for dev_id, status in statuses.items():
            if dev_id in self.device_widgets:
                widget_info = self.device_widgets[dev_id]
                switch_key = 'switch_1' if widget_info['category'] == 'tdq' else 'switch_fan'
                is_on = status.get(switch_key, False)
                
                # Update individual device status
                widget_info['status'].configure(
                    text="ON" if is_on else "OFF",
                    text_color="green" if is_on else "gray"
                )
                
                if widget_info['category'] == 'fskg':
                    fan_states.append(is_on)
                    if 'fan_speed' in status and 'slider' in widget_info:
                        widget_info['slider'].set(status['fan_speed'])
                        self.update_speed_label(widget_info['speed_label'], status['fan_speed'])
                else:
                    light_states.append(is_on)

        # Update category statuses
        self.update_category_status(self.fans_status, "Fans", fan_states)
        self.update_category_status(self.lights_status, "Lights", light_states)
        self.update_category_status(self.all_status, "All", fan_states + light_states)

    def update_category_status(self, label, category, states):
        if not states:
            status = "Unknown"
            color = "gray"
        elif all(states):
            status = "ON"
            color = "green"
        elif any(states):
            status = "MIXED"
            color = "orange"
        else:
            status = "OFF"
            color = "gray"
        
        label.configure(text=f"{category}: {status}", text_color=color)

    def toggle_category(self, category):
        for dev_id, widget_info in self.device_widgets.items():
            if widget_info['category'] == category:
                self.device_action(
                    dev_id,
                    'switch_fan' if category == 'fskg' else 'switch_1',
                    True,
                    widget_info['button']
                )

    def toggle_all_devices(self):
        for dev_id, widget_info in self.device_widgets.items():
            cmd = 'switch_fan' if widget_info['category'] == 'fskg' else 'switch_1'
            self.device_action(dev_id, cmd, True, widget_info['button'])

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    CloudUI().run()

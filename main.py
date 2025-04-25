import customtkinter as ctk
from tuya_connector import TuyaOpenAPI
import json
import darkdetect
from dotenv import load_dotenv
import os
from PIL import Image
import pystray
from pathlib import Path
import shutil
import sys
from datetime import datetime, timedelta
import threading
import time
from fan_config import get_normal_speed, get_normalize_display_text

# Try to import optional dependencies
try:
    import winshell
    from win32com.client import Dispatch
    STARTUP_AVAILABLE = True
except ImportError:
    print("Startup feature unavailable. Install winshell and pywin32 to enable.")
    STARTUP_AVAILABLE = False

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
        """Sends a command with a specific value to a device."""
        try:
            # Directly send the command and value received
            cmd = {'commands': [{'code': command, 'value': value}]}
            print(f"Sending command: ID={device_id}, CMD={command}, VAL={value}") # Debug print
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
        self.device_widgets = {}  # Move this before any UI creation
        
        # Setup window
        self.root = ctk.CTk()
        
        self.root.title("Smart Home Control")
        self.root.geometry("1000x800")  # Wider for better layout
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)

        # Load icon from assets folder
        icon_path = get_resource_path('assets/app.ico')
        try:
            self.icon_image = Image.open(icon_path)
            self.icon_image = self.icon_image.resize((128, 128), Image.Resampling.LANCZOS)
            self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Warning: Could not load app icon ({e}), using default")
            self.icon_image = Image.new('RGBA', (128, 128), (52, 152, 219))

        self.tray_icon = pystray.Icon(
            "smart_home",
            self.icon_image,
            "Smart Home Control",
            menu=self.create_menu()
        )

        # Set appearance mode based on system
        system_mode = "dark" if darkdetect.isDark() else "light"
        ctk.set_appearance_mode(system_mode)
        ctk.set_default_color_theme("blue")
        # Main container with max width
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.main_frame.pack_propagate(False)  # Prevent shrinking
        self.main_frame.configure(width=960, fg_color=("gray95", "gray15"))  # Refined background
        
        # Main content frame
        content_frame = ctk.CTkFrame(self.main_frame)
        content_frame.pack(fill="both", expand=True)
        content_frame.configure(fg_color=("gray92", "gray17"))  # Subtle contrast

        # Title
        title = ctk.CTkLabel(
            content_frame, 
            text="Smart Home Control", 
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.pack(pady=(0, 20))

        # --- Master Controls Section (Redesigned) ---
        master_frame = ctk.CTkFrame(content_frame)
        master_frame.pack(fill="x", pady=(0, 10))

        master_card = ctk.CTkFrame(master_frame, fg_color=("gray90", "gray20"))
        master_card.pack(padx=10, pady=10, fill="x")

        master_inner = ctk.CTkFrame(master_card)
        master_inner.pack(padx=2, pady=2, fill="x")

        # Status at top first (like individual cards)
        master_status_frame = ctk.CTkFrame(master_inner, fg_color="transparent")
        master_status_frame.pack(fill="x", padx=15, pady=(10, 5))
        
        self.master_indicator = ctk.CTkFrame(
            master_status_frame,
            width=8,
            height=8,
            corner_radius=4,
            fg_color=("gray70", "gray70")
        )
        self.master_indicator.pack(side="left", padx=2)
        
        self.all_status = ctk.CTkLabel(master_status_frame, text="All: Unknown")
        self.all_status.pack(side="left", padx=(4, 0))

        # Title after status
        master_title = ctk.CTkLabel(
            master_inner,
            text="Master Controls",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        master_title.pack(fill="x", padx=15, pady=(5, 5))

        # Master action buttons
        master_buttons = ctk.CTkFrame(master_inner, fg_color="transparent")
        master_buttons.pack(fill="x", padx=15, pady=(5, 10))
        master_buttons.grid_columnconfigure((0,1), weight=1, uniform='master')

        self.master_all_on = ctk.CTkButton(
            master_buttons,
            text="Turn On All",
            width=200,  # Wider buttons
            height=32,
            corner_radius=8,
            fg_color=("#1DB954", "#1DB954"),      # Spotify green
            hover_color=("#1ED760", "#1ED760"), # Brighter green
            command=lambda: self.set_all_state(True)
        )
        
        self.master_all_off = ctk.CTkButton(
            master_buttons,
            text="Turn Off All",
            width=200,
            height=32,
            corner_radius=8,
            fg_color=("#E53935", "#E53935"),      # Material red
            hover_color=("#F44336", "#F44336"),
            command=lambda: self.set_all_state(False)
        )
        
        self.master_all_on.grid(row=0, column=0, padx=5, sticky="ew")
        self.master_all_off.grid(row=0, column=1, padx=5, sticky="ew")

        # --- Fans Section (Redesigned with consistent layout) ---
        fans_frame = ctk.CTkFrame(content_frame)
        fans_frame.pack(fill="x", pady=(10, 10))

        fans_container_frame = ctk.CTkFrame(fans_frame, fg_color="transparent")
        fans_container_frame.pack(fill="x", padx=10, pady=10)
        fans_container_frame.grid_columnconfigure(1, weight=1)

        # Master fans card - make layout consistent with other cards
        master_fans = ctk.CTkFrame(fans_container_frame, fg_color=("gray90", "gray20"))
        master_fans.grid(row=0, column=0, padx=10, pady=10, sticky="nw")
        
        fans_inner = ctk.CTkFrame(master_fans)
        fans_inner.pack(padx=2, pady=2, fill="x")

        # Status at top first (like individual cards)
        status_frame = ctk.CTkFrame(fans_inner, fg_color="transparent")
        status_frame.pack(fill="x", padx=15, pady=(10, 5))
        
        self.fans_master_indicator = ctk.CTkFrame(
            status_frame,
            width=8,
            height=8,
            corner_radius=4,
            fg_color=("gray70", "gray70")
        )
        self.fans_master_indicator.pack(side="left", padx=2)
        self.fans_master_indicator.pack_propagate(False)
        
        self.fans_status = ctk.CTkLabel(
            status_frame,
            text="Fans: Unknown",
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        self.fans_status.pack(side="left", padx=(4, 0))

        # Title after status
        fans_title = ctk.CTkLabel(
            fans_inner,
            text="All Fans",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        fans_title.pack(fill="x", padx=15, pady=(5, 5))

        fans_buttons = ctk.CTkFrame(fans_inner, fg_color="transparent")
        fans_buttons.pack(fill="x", pady=(5, 10), padx=10)

        self.master_fans_normalize = ctk.CTkButton(
            fans_buttons,
            text=get_normalize_display_text(),
            height=32,
            corner_radius=8,
            fg_color=("#4B91E2", "#3B7BCE"),
            hover_color=("#3B7BCE", "#2B6BBE"),
            command=self.normalize_fan_speeds
        )
        self.master_fans_normalize.pack(fill="x", padx=5, pady=2)
        
        self.master_fans_on = ctk.CTkButton(
            fans_buttons,
            text="Turn On All",
            height=32,
            corner_radius=8,
            fg_color=("#1DB954", "#1DB954"),
            hover_color=("#1ED760", "#1ED760"),
            command=lambda: self.set_category_state('fskg', True)
        )
        self.master_fans_on.pack(fill="x", padx=5, pady=2)
        
        self.master_fans_off = ctk.CTkButton(
            fans_buttons,
            text="Turn Off All",
            height=32,
            corner_radius=8,
            fg_color=("#E53935", "#E53935"),
            hover_color=("#F44336", "#F44336"),
            command=lambda: self.set_category_state('fskg', False)
        )
        self.master_fans_off.pack(fill="x", padx=5, pady=2)

        self.device_widgets['master_fans'] = {
            'status_indicator': self.fans_master_indicator,
            'category': 'master_fskg'
        }

        self.fans_container = ctk.CTkFrame(fans_container_frame, fg_color="transparent")
        self.fans_container.grid(row=0, column=1, sticky="nsew")

        # --- Lights Section (Redesigned with better expansion) ---
        lights_frame = ctk.CTkFrame(content_frame)
        lights_frame.pack(fill="both", expand=True, pady=(10, 0))  # Changed to fill="both"

        # Better container setup for full width
        lights_container_frame = ctk.CTkFrame(lights_frame, fg_color="transparent") 
        lights_container_frame.pack(fill="both", expand=True, padx=10, pady=10)
        lights_container_frame.grid_columnconfigure(1, weight=20)  # Much higher weight for expansion
        lights_container_frame.grid_rowconfigure(0, weight=1)

        # Master light card with consistent layout
        master_light = ctk.CTkFrame(lights_container_frame, fg_color=("gray90", "gray20"))
        master_light.grid(row=0, column=0, padx=10, pady=10, sticky="nw")
        
        light_inner = ctk.CTkFrame(master_light)
        light_inner.pack(padx=2, pady=2, fill="x")

        # Status at top first (like individual cards)
        status_frame = ctk.CTkFrame(light_inner, fg_color="transparent")
        status_frame.pack(fill="x", padx=15, pady=(10, 5))
        
        self.lights_master_indicator = ctk.CTkFrame(
            status_frame,
            width=8,
            height=8,
            corner_radius=4,
            fg_color=("gray70", "gray70")
        )
        self.lights_master_indicator.pack(side="left", padx=2)
        self.lights_master_indicator.pack_propagate(False)
        
        self.lights_status = ctk.CTkLabel(
            status_frame,
            text="Lights: Unknown",
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        self.lights_status.pack(side="left", padx=(4, 0))

        # Title after status
        lights_title = ctk.CTkLabel(
            light_inner,
            text="All Lights",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        lights_title.pack(fill="x", padx=15, pady=(5, 5))

        # Modify lights buttons section to have only 2 equal-width buttons
        lights_buttons = ctk.CTkFrame(light_inner, fg_color="transparent")
        lights_buttons.pack(fill="x", pady=(5, 10), padx=10)
        
        # Configure just 2 equal columns instead of 3
        lights_buttons.grid_columnconfigure(0, weight=1, uniform="equal_lights")
        lights_buttons.grid_columnconfigure(1, weight=1, uniform="equal_lights")
        
        # Just create two buttons - no normalize button for lights
        self.master_lights_on = ctk.CTkButton(
            lights_buttons,
            text="Turn On All",
            height=32,
            width=120,  # Wider minimum width
            corner_radius=8,
            fg_color=("#1DB954", "#1DB954"),
            hover_color=("#1ED760", "#1ED760"),
            command=lambda: self.set_category_state('tdq', True)
        )
        
        self.master_lights_off = ctk.CTkButton(
            lights_buttons,
            text="Turn Off All",
            height=32, 
            width=120,  # Wider minimum width
            corner_radius=8,
            fg_color=("#E53935", "#E53935"),
            hover_color=("#F44336", "#F44336"),
            command=lambda: self.set_category_state('tdq', False)
        )

        # Grid the two buttons to fill the entire width
        self.master_lights_on.grid(row=0, column=0, padx=5, pady=2, sticky="ew")
        self.master_lights_off.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        self.device_widgets['master_lights'] = {
            'status_indicator': self.lights_master_indicator,
            'category': 'master_tdq'
        }

        self.lights_container = ctk.CTkFrame(lights_container_frame, fg_color="transparent")
        self.lights_container.grid(row=0, column=1, sticky="nsew")
        
        columns = 4  # 4 columns of lights
        for i in range(columns):
            self.lights_container.grid_columnconfigure(i, weight=1, uniform="lights")

        for name, dev in self.ctrl.devices.items():
            if dev['category'] == 'fskg':
                self.add_fan(self.fans_container, name, dev['id']) # Pass self.fans_container
            elif dev['category'] == 'tdq':
                self.add_light(self.lights_container, name, dev['id']) # Pass self.lights_container

        expiration_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        expiration_frame.pack(fill="x", pady=(10, 0))
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
        self.update_all_statuses()
        self.cached_states = self.ctrl.get_all_statuses()

    def load_icon(self, url, size=(32, 32)):
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
        device_frame = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"))
        device_frame.pack(fill="x", padx=10, pady=5)

        content_frame = ctk.CTkFrame(device_frame)
        content_frame.pack(padx=2, pady=2, fill="x")

        top_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=15, pady=5)
        top_row.grid_columnconfigure(1, weight=1)

        status_frame = ctk.CTkFrame(top_row, fg_color="transparent") 
        status_frame.grid(row=0, column=0, padx=(5, 15))
        
        status_indicator = ctk.CTkFrame(
            status_frame,
            width=8,
            height=8,
            corner_radius=4,
            fg_color="gray"
        )
        status_indicator.pack(side="left", padx=2)
        
        status_text = ctk.CTkLabel(
            status_frame,
            text="Off",
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        status_text.pack(side="left", padx=(4, 0))

        name_label = ctk.CTkLabel(
            top_row,
            text=name,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        name_label.grid(row=0, column=1, sticky="w", padx=15)

        toggle_btn = ctk.CTkButton(
            top_row,
            text="Turn On",
            width=100,
            height=32,
            fg_color=("#1DB954", "#1DB954"),      # Spotify green
            hover_color=("#1ED760", "#1ED760"), # Brighter green
            corner_radius=8,
            command=lambda: self.device_action(dev_id, 'switch_fan', True, toggle_btn)
        )
        toggle_btn.grid(row=0, column=2, padx=5)

        slider_frame = ctk.CTkFrame(content_frame, fg_color=("gray85", "gray25"))
        slider_frame.pack(fill="x", padx=15, pady=(0, 5))

        speed_label = ctk.CTkLabel(
            slider_frame,
            text="Speed: 50%",
            font=ctk.CTkFont(size=12)
        )
        speed_label.pack(pady=(5, 0))

        slider = ctk.CTkSlider(
            slider_frame,
            from_=1,
            to=100,
            number_of_steps=99,
            height=16,
            button_color=("#1DB954", "#1DB954"),      # Spotify green
            button_hover_color=("#1ED760", "#1ED760"), # Brighter green
            progress_color=("#1DB954", "#1DB954")      # Spotify green
        )
        slider.pack(fill="x", padx=10, pady=5)

        slider.configure(command=lambda v: self.update_speed_label(speed_label, v))
        slider.bind(
            "<ButtonRelease-1>",
            lambda e: self.device_action(dev_id, 'fan_speed', int(slider.get()), None)
        )

        self.device_widgets[dev_id] = {
            'button': toggle_btn,
            'status_indicator': status_indicator,
            'status_text': status_text,
            'category': 'fskg',
            'slider': slider,
            'speed_label': speed_label,
            'default_colors': {
                'on': ("#1DB954", "#1DB954"),      # Spotify green
                'on_hover': ("#1ED760", "#1ED760"), # Brighter green
                'off': ("#E53935", "#E53935"),      # Material red
                'off_hover': ("#F44336", "#F44336") # Brighter red
            }
        }

        self.update_device_status(dev_id)

    def add_light(self, parent, name, dev_id):
        container = ctk.CTkFrame(parent, fg_color=("gray90", "gray20"))
        
        widgets = parent.grid_slaves()
        next_pos = len(widgets)
        col = next_pos % 4
        row = next_pos // 4
        
        container.grid(row=row, column=col, padx=(5, 5), pady=(5, 5), sticky="nsew")
        parent.grid_rowconfigure(row, weight=1)
        
        light_frame = ctk.CTkFrame(container)
        light_frame.pack(padx=2, pady=2, fill="both", expand=True)

        status_frame = ctk.CTkFrame(light_frame, fg_color="transparent")
        status_frame.pack(pady=(10, 2))
        
        status_indicator = ctk.CTkFrame(
            status_frame,
            width=8,
            height=8,
            corner_radius=4,
            fg_color="gray"
        )
        status_indicator.pack(side="left", padx=2)
        status_indicator.pack_propagate(False)
        
        status_text = ctk.CTkLabel(
            status_frame,
            text="Off",
            font=ctk.CTkFont(size=11),
            text_color="gray70"
        )
        status_text.pack(side="left", padx=(4, 0))

        name_label = ctk.CTkLabel(
            light_frame,
            text=name,
            font=ctk.CTkFont(size=16, weight="bold")
        )
        name_label.pack(pady=(2, 5))

        toggle_btn = ctk.CTkButton(
            light_frame,
            text=f"Turn On",
            width=120,
            height=32,
            corner_radius=8,
            fg_color=("#1DB954", "#1DB954"),
            hover_color=("#1ED760", "#1ED760"),
            command=lambda: self.device_action(dev_id, 'switch_1', True, toggle_btn)
        )
        toggle_btn.pack(fill="x", pady=(0, 10), padx=10)

        self.device_widgets[dev_id] = {
            'button': toggle_btn,
            'status_indicator': status_indicator,
            'status_text': status_text,
            'category': 'tdq',
            'name': name,
            'default_colors': {
                'on': ("#1DB954", "#1DB954"),
                'on_hover': ("#1ED760", "#1ED760"),
                'off': ("#E53935", "#E53935"),
                'off_hover': ("#F44336", "#F44336")
            }
        }

        self.update_device_status(dev_id)

    def update_speed_label(self, label, value):
        label.configure(text=f"{int(value)}%")

    def device_action(self, dev_id, cmd, value, widget=None, force_state=False):
        orig_hover = widget.cget("hover_color") if widget else None
        default_fg = self.device_widgets.get(dev_id, {}).get('default_fg') if widget else None

        final_value = value

        if not force_state and cmd in ['switch_1', 'switch_fan']:
            status = self.ctrl.get_device_status(dev_id)
            if status:
                current_state = status.get(cmd, False)
                final_value = not current_state
                print(f"Toggling {dev_id}: Current={current_state}, New={final_value}")
            else:
                print(f"Could not get status for {dev_id}, skipping toggle.")
                if widget and default_fg:
                     widget.configure(fg_color=default_fg, hover_color=orig_hover)
                return

        if cmd != 'fan_speed':
             actual_value_to_send = bool(final_value)
        else:
             actual_value_to_send = int(value)
        
        print(f"Calling API for {dev_id}: cmd={cmd}, value={actual_value_to_send}, force={force_state}")

        result = self.ctrl.control(dev_id, cmd, actual_value_to_send)

        if result.get('success'):
            widget_info = self.device_widgets.get(dev_id, {})
            is_on = actual_value_to_send if cmd != 'fan_speed' else widget_info.get('last_state', False)
            
            widget_info['last_state'] = is_on
            
            self._update_device_ui(dev_id, widget_info, is_on)
            
            if widget:
                orig_hover = widget.cget("hover_color")
                widget.configure(fg_color="green", hover_color="green")
                self.root.after(750, lambda: widget.configure(hover_color=orig_hover))

            self.cached_states = self.ctrl.get_all_statuses()

            self.root.after(2000, self.update_all_statuses)
        else:
            if widget:
                orig_fg = widget.cget("fg_color")
                orig_hover = widget.cget("hover_color")
                widget.configure(fg_color="red", hover_color="red")
                self.root.after(750, lambda: widget.configure(
                    fg_color=orig_fg, hover_color=orig_hover
                ))

    def _update_device_ui(self, dev_id, widget_info, is_on):
        colors = widget_info.get('default_colors', {})
        
        status_color = ("#1DB954", "#1DB954") if is_on else ("gray70", "gray70")
        
        if 'status_indicator' in widget_info:
            widget_info['status_indicator'].configure(fg_color=status_color)
            
            # Update category indicators
            if widget_info['category'] == 'tdq':
                all_lights = [w for w in self.device_widgets.values() if w.get('category') == 'tdq']
                all_on = all(w.get('last_state', False) for w in all_lights)
                master_color = ("#1DB954", "#1DB954") if all_on else ("gray70", "gray70")
                self.lights_master_indicator.configure(fg_color=master_color)
            elif widget_info['category'] == 'fskg':
                all_fans = [w for w in self.device_widgets.values() if w.get('category') == 'fskg']
                all_on = all(w.get('last_state', False) for w in all_fans)
                master_color = ("#1DB954", "#1DB954") if all_on else ("gray70", "gray70")
                self.fans_master_indicator.configure(fg_color=master_color)
            
            # Update the main master indicator - check if ALL devices are on
            all_devices = [w for w in self.device_widgets.values() 
                           if w.get('category') in ['tdq', 'fskg']]
            all_master_on = all(w.get('last_state', False) for w in all_devices)
            master_indicator_color = ("#1DB954", "#1DB954") if all_master_on else ("gray70", "gray70")
            self.master_indicator.configure(fg_color=master_indicator_color)

        if widget_info['category'] == 'tdq':
            toggle_btn = widget_info.get('button')
            if toggle_btn:
                if is_on:
                    toggle_btn.configure(
                        text="Turn Off",
                        fg_color=colors.get('off', ("#E53935", "#E53935")),
                        hover_color=colors.get('off_hover', ("#F44336", "#F44336"))
                    )
                else:
                    toggle_btn.configure(
                        text="Turn On",
                        fg_color=colors.get('on', ("#1DB954", "#1DB954")),
                        hover_color=colors.get('on_hover', ("#1ED760", "#1ED760"))
                    )

        elif widget_info['category'] == 'fskg':
            toggle_btn = widget_info.get('button')
            if toggle_btn and colors:
                if is_on:
                    toggle_btn.configure(
                        text="Turn Off",
                        fg_color=colors['off'],
                        hover_color=colors['off_hover']
                    )
                else:
                    toggle_btn.configure(
                        text="Turn On",
                        fg_color=colors['on'],
                        hover_color=colors['on_hover']
                    )

    def update_device_status(self, dev_id):
        status = self.ctrl.get_device_status(dev_id)
        if status and dev_id in self.device_widgets:
            widget_info = self.device_widgets[dev_id]
            is_on = status.get('switch_1' if widget_info['category'] == 'tdq' else 'switch_fan', False)
            
            widget_info['last_state'] = is_on
            
            self._update_device_ui(dev_id, widget_info, is_on)
            
            if widget_info['category'] == 'fskg' and 'fan_speed' in status:
                if 'slider' in widget_info:
                    speed = status['fan_speed']
                    widget_info['slider'].set(speed)
                    self.update_speed_label(widget_info['speed_label'], speed)

    def update_all_statuses(self):
        statuses = self.ctrl.get_all_statuses()
        fan_states = []
        light_states = []
        
        for dev_id, status in statuses.items():
            if dev_id in self.device_widgets:
                self.update_device_status(dev_id)
                
                widget_info = self.device_widgets[dev_id]
                switch_key = 'switch_1' if widget_info['category'] == 'tdq' else 'switch_fan'
                is_on = status.get(switch_key, False)
                
                if widget_info['category'] == 'fskg':
                    fan_states.append(is_on)
                else:
                    light_states.append(is_on)

        self.update_category_status(self.fans_status, "Fans", fan_states)
        self.update_category_status(self.lights_status, "Lights", light_states)
        self.update_category_status(self.all_status, "All", fan_states + light_states)

    def update_category_status(self, label, category, states):
        if not states:
            status = "Unknown"
            color = "gray"
            show_buttons = "both"
        elif all(states):
            status = "ON"
            color = "green"
            show_buttons = "off"
        elif any(states):
            status = "MIXED"
            color = "orange"
            show_buttons = "both"
        else:
            status = "OFF"
            color = "gray"
            show_buttons = "on"

        label.configure(text=f"{category}: {status}", text_color=color)
        
        if category == "All":
            self.master_all_on.grid_remove()
            self.master_all_off.grid_remove()
            if show_buttons in ["both", "on"]:
                self.master_all_on.grid(row=0, column=0, columnspan=2 if show_buttons == "on" else 1, padx=5, sticky="ew")
            if show_buttons in ["both", "off"]:
                column = 1 if show_buttons == "both" else 0
                self.master_all_off.grid(row=0, column=column, columnspan=2 if show_buttons == "off" else 1, padx=5, sticky="ew")
        elif category == "Fans":
            if show_buttons == "both":
                self.master_fans_normalize.pack(fill="x", padx=5, pady=2)
                self.master_fans_on.pack(fill="x", padx=5, pady=2)
                self.master_fans_off.pack(fill="x", padx=5, pady=2)
            elif show_buttons == "on":
                self.master_fans_normalize.pack(fill="x", padx=5, pady=2)
                self.master_fans_on.pack(fill="x", padx=5, pady=2)
                self.master_fans_off.pack_forget()
            else:
                self.master_fans_normalize.pack(fill="x", padx=5, pady=2)
                self.master_fans_on.pack_forget()
                self.master_fans_off.pack(fill="x", padx=5, pady=2)
        elif category == "Lights":
            # Use grid_remove() and grid() instead of pack for lights buttons
            self.master_lights_on.grid_remove()
            self.master_lights_off.grid_remove()
            
            if show_buttons == "both":
                # Show both buttons filling space equally
                self.master_lights_on.grid(row=0, column=0, padx=5, pady=2, sticky="ew")
                self.master_lights_off.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
            elif show_buttons == "on":
                # Just show ON button filling entire width
                self.master_lights_on.grid(row=0, column=0, columnspan=2, padx=5, pady=2, sticky="ew")
            else:
                # Just show OFF button filling entire width
                self.master_lights_off.grid(row=0, column=0, columnspan=2, padx=5, pady=2, sticky="ew")

    def _run_concurrent_actions(self, actions):
        threads = []
        for action_args in actions:
            dev_id, cmd, value, force_state = action_args
            thread_args = (dev_id, cmd, value, None, force_state)
            thread = threading.Thread(target=self.device_action, args=thread_args, daemon=True)
            threads.append(thread)
            thread.start()
            time.sleep(0.05) 
            
        self.root.after(3000, self.update_all_statuses)
        self.root.after(3500, self.update_tray_menu)

    def set_category_state(self, category, state: bool):
        actions_to_run = []
        for dev_id, widget_info in self.device_widgets.items():
            if widget_info['category'] == category:
                cmd = 'switch_fan' if category == 'fskg' else 'switch_1'
                actions_to_run.append((dev_id, cmd, state, True))

        if actions_to_run:
            self._run_concurrent_actions(actions_to_run)
            feedback_widget = None
            if category == 'fskg': feedback_widget = self.master_fans_on if state else self.master_fans_off
            elif category == 'tdq': feedback_widget = self.master_lights_on if state else self.master_lights_off
            if feedback_widget:
                 orig_fg = feedback_widget.cget("fg_color")
                 orig_hover = feedback_widget.cget("hover_color")
                 feedback_widget.configure(fg_color="orange", hover_color="orange")
                 self.root.after(1500, lambda: feedback_widget.configure(fg_color=orig_fg, hover_color=orig_hover))

    def set_all_state(self, state: bool):
        actions_to_run = []
        for dev_id, widget_info in self.device_widgets.items():
            cmd = 'switch_fan' if widget_info['category'] == 'fskg' else 'switch_1'
            actions_to_run.append((dev_id, cmd, state, True))

        if actions_to_run:
            self._run_concurrent_actions(actions_to_run)
            feedback_widget = self.master_all_on if state else self.master_all_off
            orig_fg = feedback_widget.cget("fg_color")
            orig_hover = feedback_widget.cget("hover_color")
            feedback_widget.configure(fg_color="orange", hover_color="orange")
            self.root.after(1500, lambda: feedback_widget.configure(fg_color=orig_fg, hover_color=orig_hover))

    def normalize_fan_speeds(self):
        actions_to_run = []
        for dev_id, widget_info in self.device_widgets.items():
            if widget_info['category'] == 'fskg':
                status = self.ctrl.get_device_status(dev_id)
                if status and status.get('switch_fan', False):
                    device_name = [name for name, dev in self.ctrl.devices.items() 
                                if dev['id'] == dev_id][0]
                    normal_speed = get_normal_speed(device_name)
                    actions_to_run.append((dev_id, 'fan_speed', normal_speed, True))
        
        if actions_to_run:
            self._run_concurrent_actions(actions_to_run)
            
        self.master_fans_normalize.configure(
            text="Normalize (E:40%/F:45%)"
        )

    def hide_window(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def toggle_window(self, _=None):
        if threading.current_thread() is not threading.main_thread():
            self.root.after(0, self._toggle_window_thread_safe)
        else:
            self._toggle_window_thread_safe()

    def _toggle_window_thread_safe(self):
        if self.root.state() == 'withdrawn':
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        else:
            self.root.withdraw()

    def reset_window_position(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 800) // 2
        y = (screen_height - 600) // 2
        self.root.geometry(f"800x600+{x}+{y}")
        self.show_window()

    def is_startup_enabled(self):
        startup_path = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_path, "TuyaSmartHome.lnk")
        return os.path.exists(shortcut_path)

    def toggle_startup(self, _=None):
        if not STARTUP_AVAILABLE:
            print("Startup feature not available")
            return
            
        try:
            startup_path = os.path.join(
                os.environ['APPDATA'],
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            shortcut_path = os.path.join(startup_path, "TuyaSmartHome.lnk")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            exe_path = os.path.normpath(os.path.join(script_dir, 'dist', 'TuyaSmart Control.exe'))
            
            if self.is_startup_enabled():
                os.remove(shortcut_path)
                print(f"Removed startup shortcut: {shortcut_path}")
            else:
                if not os.path.exists(exe_path):
                    print(f"Error: Executable not found at {exe_path}")
                    return
                    
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = exe_path
                shortcut.WorkingDirectory = os.path.dirname(exe_path)
                shortcut.save()
                print(f"Created startup shortcut: {shortcut_path}")
                print(f"Target: {exe_path}")

            self.update_tray_menu()
        except Exception as e:
            print(f"Failed to toggle startup: {e}")

    def create_menu(self):
        def make_device_toggle(dev_id, cmd):
            def toggle(_):
                status = self.ctrl.get_device_status(dev_id)
                current = status.get(cmd, False) if status else False
                self.device_action(dev_id, cmd, not current, None, True)
            return toggle

        devices_menu = [
            pystray.MenuItem('Show/Hide', self.toggle_window, default=True),
            pystray.Menu.SEPARATOR
        ]

        fans = [(name, dev) for name, dev in self.ctrl.devices.items() 
                if dev['category'] == 'fskg']
        if fans:
            for name, dev in fans:
                devices_menu.append(
                    pystray.MenuItem(name, make_device_toggle(dev['id'], 'switch_fan'))
                )
            devices_menu.append(pystray.Menu.SEPARATOR)

        lights = [(name, dev) for name, dev in self.ctrl.devices.items() 
                 if dev['category'] == 'tdq']
        if lights:
            for name, dev in lights:
                devices_menu.append(
                    pystray.MenuItem(name, make_device_toggle(dev['id'], 'switch_1'))
                )
            devices_menu.append(pystray.Menu.SEPARATOR)

        if fans:
            devices_menu.append(
                pystray.MenuItem('Normalize Fan Speeds', 
                    lambda _: self.normalize_fan_speeds())
            )
            devices_menu.append(pystray.Menu.SEPARATOR)

        master_menu = pystray.Menu(
            pystray.MenuItem('Turn On Everything', lambda _: self.set_all_state(True)),
            pystray.MenuItem('Turn Off Everything', lambda _: self.set_all_state(False)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Turn On All Fans', lambda _: self.set_category_state('fskg', True)),
            pystray.MenuItem('Turn Off All Fans', lambda _: self.set_category_state('fskg', False)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Turn On All Lights', lambda _: self.set_category_state('tdq', True)),
            pystray.MenuItem('Turn Off All Lights', lambda _: self.set_category_state('tdq', False))
        )
        devices_menu.append(pystray.MenuItem('Master Controls', master_menu))
        devices_menu.append(pystray.Menu.SEPARATOR)

        devices_menu.extend([
            pystray.MenuItem('Run at Startup', self.toggle_startup,
                checked=lambda _: self.is_startup_enabled()) if STARTUP_AVAILABLE else None,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', self.quit_application)
        ])

        return pystray.Menu(*[item for item in devices_menu if item is not None])

    def update_tray_menu(self):
        if hasattr(self, 'tray_icon'):
            self.tray_icon.menu = self.create_menu()

    def quit_application(self):
        self.tray_icon.stop()
        self.root.quit()

    def run(self):
        def run_tray():
            try:
                self.tray_icon.run()
            except Exception as e:
                print(f"Tray icon error: {e}")
        
        threading.Thread(target=run_tray, daemon=True).start()
        time.sleep(0.1)
        self.root.deiconify()
        self.root.mainloop()

if __name__ == "__main__":
    app = CloudUI()
    app.run()

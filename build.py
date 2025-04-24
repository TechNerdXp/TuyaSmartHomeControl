import PyInstaller.__main__
import os
from pathlib import Path

project_root = Path(__file__).parent

# Use a simple built-in PyInstaller icon since we're setting it at runtime anyway
PyInstaller.__main__.run([
    'main.py',
    '--name=TuyaSmartControl',
    '--windowed',
    '--onefile',
    '--clean',
    '--add-data=devices.json;.',
    '--add-data=assets;assets',
    '--collect-all=customtkinter',
    '--hidden-import=PIL._tkinter_finder',
])

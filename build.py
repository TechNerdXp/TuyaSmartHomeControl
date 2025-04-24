import PyInstaller.__main__
import os
from pathlib import Path

project_root = Path(__file__).parent

# Use app.ico for both runtime and exe icon
PyInstaller.__main__.run([
    'main.py',
    '--name=TuyaSmart Control',
    '--windowed',
    '--onefile',
    '--clean',
    '--icon=assets/app.ico',  # Add icon for exe
    '--add-data=devices.json;.',
    '--add-data=assets;assets',
    '--collect-all=customtkinter',
    '--hidden-import=PIL._tkinter_finder',
])

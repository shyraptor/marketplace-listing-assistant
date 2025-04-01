# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# Main application files to be included in the executable
a = Analysis(
    ['frontend.py'],  # Main entry point
    pathex=[],
    binaries=[],
    datas=[
        ('icon.ico', '.'),  # Include icon file in the root directory
        ('bg/*', 'bg')
    ],
    hiddenimports=[
        'backend',         # Ensure backend module is included
        'PIL',
        'PIL._tkinter_finder',
        'rembg',
        'pyperclip',
        'ttkbootstrap',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Create the EXE
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # Use a folder structure rather than single file
    name='vinted_seller_studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',  # Set application icon
)

# External files to be included alongside the executable (not bundled inside)
# These need to remain write-accessible
external_files = [
    # Config files
    ('config.json', '.'),
    ('templates.json', '.'),
    ('hashtag_mapping.json', '.'),
    
    # Include language folder and all its contents
    ('lang', 'lang'),
    
    # Include backgrounds folder and all its contents
    ('bg', 'bg'),
]

# Create the distribution package
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='vinted_seller_studio',
)

# Add the external files to the distribution folder at build time
# This is a simpler approach that doesn't depend on PyInstaller internals
import os
import shutil

# Function to copy external files to the dist folder
def copy_external_files():
    dist_dir = os.path.join('dist', 'vinted_seller_studio')
    
    # Create distribution directory if it doesn't exist
    if not os.path.exists(dist_dir):
        os.makedirs(dist_dir)
    
    for src, dst in external_files:
        src_path = src
        dst_path = os.path.join(dist_dir, dst)
        
        # Create destination directory if needed
        dst_dir = os.path.dirname(dst_path)
        if dst_dir and not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
        
        # Copy file or directory
        if os.path.isdir(src_path):
            # If directory doesn't exist, create it
            if not os.path.exists(dst_path):
                os.makedirs(dst_path)
            
            # Copy all files in the directory
            for item in os.listdir(src_path):
                s = os.path.join(src_path, item)
                d = os.path.join(dst_path, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)
        else:
            # Copy file
            shutil.copy2(src_path, dst_path)
    
    print("External files copied successfully.")

# Execute the copy function
copy_external_files()
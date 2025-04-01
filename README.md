# Vinted Seller Studio

![License](https://img.shields.io/badge/license-GPLv3-blue)

**A desktop application for Vinted sellers to prepare professional product listings with background replacement, tag management, and description generation.**

## 🌟 Overview

Vinted Seller Studio helps sellers create professional-looking product listings by automating background replacement, organizing measurements, generating hashtags, and formatting descriptions for optimal marketplace visibility.

*This has been mostly "vibe coded" with the assistance of AI.*

## ✨ Features

- **Background Removal** - Automatically remove backgrounds from clothing photos
- **Custom Backgrounds** - Apply solid color or image backgrounds that complement your items
- **Multi-Project Management** - Organize multiple clothing listings simultaneously
- **Measurement Templates** - Pre-defined templates for different clothing types (shirts, pants, coats, etc.)
- **Tag System** - Easily add relevant tags and hashtags to boost visibility
- **Color Management** - Categorize items by color with visual color swatches
- **Description Generation** - Automatically format professional item descriptions
- **Multi-language Support** - Easily switch between languages
- **Image Adjustments** - Fine-tune image positioning, size, and orientation
- **Batch Processing** - Process multiple images at once

## 📋 Requirements
*Note: This application was developed and tested on Windows 10 64-bit.*

### To run from source:
- Python 3.7+
- Required packages:
  - Pillow (PIL fork)
  - rembg
  - tkinter
  - ttkbootstrap
  - pyperclip

## ⚙️ Installation

### Option 1: Executable (.exe)
1. Download the latest release from the [Releases page](https://github.com/shyraptor/vinted-seller-studio/releases)
2. Extract the zip file
3. Ensure the following files/folders are in the same directory as the .exe:
   - `config.json`
   - `templates.json`
   - `hashtag_mapping.json`
   - `lang` folder
   - `bg` folder 
4. Run `vinted_seller_studio.exe`

> **⚠️ Important Note:** The application may take longer to start the first time you run it. This is normal behavior as it needs to initialize resources and prepare the environment. Subsequent launches will be significantly faster.

### Option 2: From Source
1. Clone the repository:
   ```
   git clone https://github.com/shyraptor/vinted-seller-studio.git
   ```

2. Install dependencies:
   ```
   pip install Pillow rembg tkinter ttkbootstrap pyperclip
   ```

3. Run the application:
   ```
   python frontend.py
   ```

## 🚀 User Guide

### Quick Start
1. Launch the application
2. Add images with "➕ Images" 
3. Select clothing type from the dropdown
4. Click "✨ Process" to remove backgrounds
5. Adjust individual images if needed
6. Add tags and measurements
7. Click "📝 Generate" to create description
8. Click "💾 Save" to export processed images and description

### Detailed Instructions

#### Managing Projects
- Use "➕ Project" to create a new project
- Navigate between projects with the "<" and ">" buttons
- Remove projects with "🗑️ Project"

#### Adding & Processing Images
- Add images to the current project with "➕ Images"
- Load multiple projects from a zip file with "📦 Zip"
- Process all images with "✨ Process"
- Click on a processed image to select it for adjustments
- Remove individual images with the "🗑️" button

#### Adjusting Images
- Set vertical/horizontal position with sliders
- Adjust size with the size slider
- Toggle between solid color and image backgrounds
- Select a specific background from the dropdown
- Toggle horizontal/vertical orientation

#### Adding Product Details
- Select the clothing type from the dropdown
- Enter condition description
- Fill in measurements based on the selected clothing type
- Select relevant tags from the tag sections
- Add custom hashtags in comma-separated format
- Add storage info if needed

#### Generating & Saving
- Click "📝 Generate" to create the description
- Copy the description with "✂️ Copy Description"
- Save processed images and description with "💾 Save"

#### Settings & Customization
- Open settings with "⚙️ Settings"
- Configure clothing types, tags, colors, and backgrounds
- Add new background images
- Change language settings (requires restart)
- Adjust canvas dimensions

## 📸 Background Preparation

The application comes with several pre-prepared backgrounds, but you can add your own in two ways:

1. **Through the Settings Interface:**
   - Click "⚙️ Settings" and navigate to the "🏞️ Backgrounds" tab
   - Use "Add Background Files..." to select individual images
   - Or use "Import from folder" to add multiple backgrounds at once
   - Remove backgrounds using the "Remove Selected" button

2. **Directly to the folder:**
   - Navigate to the "bg" folder
   - Add your background images (JPG, PNG, or WEBP format)
   - Backgrounds will automatically appear in the dropdown menu

## 📄 License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0) - see the LICENSE file for details.

## 🙏 Acknowledgements

- [rembg](https://github.com/danielgatis/rembg) for background removal functionality
- [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap) for the modern UI components

---

**Disclaimer:** This application is not affiliated with, endorsed by, or connected to Vinted in any way. It's just a helpful tool for sellers to prepare their listings.

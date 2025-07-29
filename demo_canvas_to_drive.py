#!/usr/bin/env python3
"""
Demo script: Canvas to Google Drive File Transfer

This script demonstrates how to:
1. Connect to Canvas API
2. Fetch files from a specific course
3. Download files from Canvas
4. Upload files to Google Drive folders

Usage:
    python demo_canvas_to_drive.py
"""

import asyncio
import aiohttp
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from canvas_client import CanvasClient
from drive_client import GoogleDriveClient
from config import Config


async def list_course_files(canvas_client: CanvasClient, course_id: int) -> list:
    """Get all files from a course by scanning modules.
    
    Args:
        canvas_client: Initialized Canvas client
        course_id: Canvas course ID
        
    Returns:
        list: List of file items found in the course
    """
    print(f"🔍 Scanning course {course_id} for files...")
    
    files_found = []
    
    async with aiohttp.ClientSession() as session:
        # Get all modules in the course
        modules = await canvas_client.get_modules(session, course_id)
        print(f"Found {len(modules)} modules")
        
        for module in modules:
            module_id = module.get('id')
            module_name = module.get('name', 'Unknown Module')
            print(f"  📁 Checking module: {module_name}")
            
            # Get items in each module
            items = await canvas_client.get_module_items_with_session(session, course_id, module_id)
            
            for item in items:
                if item.get('type') == 'File':
                    file_info = {
                        'module_name': module_name,
                        'title': item.get('title', 'Unknown File'),
                        'content_id': item.get('content_id'),
                        'url': item.get('html_url'),
                        'item': item
                    }
                    files_found.append(file_info)
                    print(f"    📄 Found file: {file_info['title']}")
    
    return files_found


def select_google_drive_folder(drive_client: GoogleDriveClient) -> str:
    """Let user select a Google Drive folder for uploads.
    
    Args:
        drive_client: Initialized Google Drive client
        
    Returns:
        str: Selected folder ID, or None for root
    """
    print("\n📂 Available Google Drive folders:")
    folders = drive_client.get_all_folders()
    
    if not folders:
        print("No folders found. Files will be uploaded to Drive root.")
        return None
    
    # Display folders with numbers
    print("0. Root folder (My Drive)")
    for i, folder in enumerate(folders, 1):
        print(f"{i}. {folder['name']}")
    
    while True:
        try:
            choice = input(f"\nSelect folder (0-{len(folders)}): ").strip()
            choice_num = int(choice)
            
            if choice_num == 0:
                return None  # Root folder
            elif 1 <= choice_num <= len(folders):
                selected_folder = folders[choice_num - 1]
                print(f"✅ Selected folder: {selected_folder['name']}")
                return selected_folder['id']
            else:
                print("❌ Invalid selection. Please try again.")
        except ValueError:
            print("❌ Please enter a valid number.")


async def transfer_files_demo():
    """Main demo function to transfer files from Canvas to Google Drive."""
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Canvas to Google Drive File Transfer Demo")
    print("=" * 50)
    
    # Step 1: Initialize Google Drive client
    print("\n1️⃣ Initializing Google Drive connection...")
    drive_client = GoogleDriveClient()
    
    if not drive_client.authenticate():
        print("❌ Failed to authenticate with Google Drive.")
        print("Make sure you have credentials.json in the project root.")
        return
    
    print("✅ Google Drive authentication successful!")
    
    # Step 2: Initialize Canvas client
    print("\n2️⃣ Initializing Canvas connection...")
    try:
        canvas_client = CanvasClient(drive_client=drive_client)
        print("✅ Canvas client initialized!")
    except Exception as e:
        print(f"❌ Failed to initialize Canvas client: {e}")
        print("Make sure CANVAS_API_TOKEN is set in your .env file.")
        return
    
    # Step 3: Get course ID from user
    print("\n3️⃣ Course Selection")
    try:
        # Try to get active courses first
        active_courses = await canvas_client.get_active_courses()
        if active_courses:
            print("Your active courses:")
            for course in active_courses[:5]:  # Show first 5
                print(f"  - {course['name']} (ID: {course['id']})")
    except Exception as e:
        print(f"⚠️  Could not fetch active courses: {e}")
    
    while True:
        try:
            course_id_input = input("\nEnter Canvas course ID: ").strip()
            course_id = int(course_id_input)
            break
        except ValueError:
            print("❌ Please enter a valid course ID number.")
    
    # Step 4: Get course info and files
    print(f"\n4️⃣ Fetching course information...")
    try:
        course_info = await canvas_client.get_course(course_id)
        if course_info:
            course_name = course_info.get('name', f'Course {course_id}')
            print(f"✅ Found course: {course_name}")
        else:
            print(f"⚠️  Course {course_id} not found or not accessible")
            course_name = f'Course {course_id}'
    except Exception as e:
        print(f"⚠️  Error fetching course info: {e}")
        course_name = f'Course {course_id}'
    
    # Step 5: Find files in course
    files_found = await list_course_files(canvas_client, course_id)
    
    if not files_found:
        print("❌ No files found in the course modules.")
        return
    
    print(f"\n✅ Found {len(files_found)} files in the course!")
    
    # Step 6: Select Google Drive folder
    print("\n5️⃣ Google Drive Folder Selection")
    target_folder_id = select_google_drive_folder(drive_client)
    
    # Step 7: Transfer files
    print(f"\n6️⃣ Transferring Files")
    print("=" * 30)
    
    successful_transfers = 0
    failed_transfers = 0
    
    async with aiohttp.ClientSession() as session:
        for i, file_info in enumerate(files_found, 1):
            print(f"\n[{i}/{len(files_found)}] Processing: {file_info['title']}")
            print(f"    Module: {file_info['module_name']}")
            
            try:
                # Download and upload file
                result = await canvas_client.get_file_content(
                    session=session,
                    file_id=file_info['content_id'],
                    folder_id=target_folder_id
                )
                
                if result and result.get('upload_success'):
                    successful_transfers += 1
                    print(f"    ✅ Successfully uploaded!")
                    print(f"    📁 Google Drive: {result['drive_url']}")
                    print(f"    📊 Size: {result['size']:,} bytes")
                elif result:
                    failed_transfers += 1
                    print(f"    ⚠️  Downloaded but upload failed")
                    print(f"    📄 File: {result['filename']}")
                else:
                    failed_transfers += 1
                    print(f"    ❌ Failed to download file")
                    
            except Exception as e:
                failed_transfers += 1
                print(f"    ❌ Error: {e}")
    
    # Step 8: Summary
    print(f"\n7️⃣ Transfer Summary")
    print("=" * 20)
    print(f"✅ Successful transfers: {successful_transfers}")
    print(f"❌ Failed transfers: {failed_transfers}")
    print(f"📊 Total files processed: {len(files_found)}")
    
    if successful_transfers > 0:
        print(f"\n🎉 Files successfully uploaded to Google Drive!")
    
    print("\n✨ Demo completed!")


if __name__ == "__main__":
    try:
        asyncio.run(transfer_files_demo())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
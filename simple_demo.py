#!/usr/bin/env python3
"""
Simple Canvas to Google Drive File Transfer Demo

Fetches files from course 213007 and uploads them to Google Drive.
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


def select_google_drive_folder(drive_client: GoogleDriveClient) -> str:
    """Let user select a Google Drive folder for uploads."""
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


async def main():
    """Main function to transfer files from Canvas course 213007 to Google Drive."""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Fixed course ID
    COURSE_ID = 213007
    
    print("🚀 Canvas to Google Drive File Transfer")
    print(f"📚 Course ID: {COURSE_ID}")
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
    
    # Step 3: Get course info
    print(f"\n3️⃣ Fetching course information...")
    try:
        course_info = await canvas_client.get_course(COURSE_ID)
        if course_info:
            course_name = course_info.get('name', f'Course {COURSE_ID}')
            print(f"✅ Found course: {course_name}")
        else:
            print(f"⚠️  Course {COURSE_ID} not found or not accessible")
            course_name = f'Course {COURSE_ID}'
    except Exception as e:
        print(f"⚠️  Error fetching course info: {e}")
        course_name = f'Course {COURSE_ID}'
    
    # Step 4: Find files in course modules
    print(f"\n4️⃣ Scanning course {COURSE_ID} for files...")
    files_found = []
    
    async with aiohttp.ClientSession() as session:
        try:
            # Get all modules in the course
            modules = await canvas_client.get_modules(session, COURSE_ID)
            print(f"Found {len(modules)} modules")
            
            for module in modules:
                module_id = module.get('id')
                module_name = module.get('name', 'Unknown Module')
                print(f"  📁 Checking module: {module_name}")
                
                # Get items in each module
                items = await canvas_client.get_module_items_with_session(session, COURSE_ID, module_id)
                
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
        except Exception as e:
            print(f"❌ Error scanning course: {e}")
            return
    
    if not files_found:
        print("❌ No files found in the course modules.")
        return
    
    print(f"\n✅ Found {len(files_found)} files in the course!")
    
    # Step 5: Select Google Drive folder
    print("\n5️⃣ Google Drive Folder Selection")
    target_folder_id = select_google_drive_folder(drive_client)
    
    # Step 6: Transfer files
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
    
    # Step 7: Summary
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
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
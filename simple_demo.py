#!/usr/bin/env python3
"""
Simple Canvas to Google Drive File Transfer Demo

Fetches files from multiple Canvas courses and uploads them to Google Drive.
Now includes duplicate file detection - files with the same name are automatically skipped!
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



async def main():
    """Main function to transfer files from multiple Canvas courses to Google Drive."""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Multiple course IDs
    COURSE_IDS = [213800, 214943, 213007]
    
    print("🚀 Canvas to Google Drive File Transfer")
    print(f"📚 Course IDs: {COURSE_IDS}")
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
    
    # Step 3: Get default folder (UniMelb-2025-S2)
    print("\n3️⃣ Getting default folder (UniMelb-2025-S2)")
    target_folder_id = drive_client.get_folder_id()
    if target_folder_id:
        print("✅ Found UniMelb-2025-S2 folder")
    else:
        print("❌ UniMelb-2025-S2 folder not found. Files will be uploaded to Drive root.")
    
    # Step 4: Process each course
    all_files_found = []
    
    async with aiohttp.ClientSession() as session:
        for course_idx, course_id in enumerate(COURSE_IDS, 1):
            print(f"\n4️⃣.{course_idx} Processing Course {course_id}")
            print("=" * 40)
            
            # Get course info
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
            
            # Find files in course modules
            print(f"🔍 Scanning course {course_id} for files...")
            course_files = []
            
            try:
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
                                'course_id': course_id,
                                'course_name': course_name,
                                'module_name': module_name,
                                'title': item.get('title', 'Unknown File'),
                                'content_id': item.get('content_id'),
                                'url': item.get('html_url'),
                                'item': item
                            }
                            course_files.append(file_info)
                            print(f"    📄 Found file: {file_info['title']}")
                
                print(f"✅ Found {len(course_files)} files in {course_name}")
                all_files_found.extend(course_files)
                
            except Exception as e:
                print(f"❌ Error scanning course {course_id}: {e}")
                continue
    
    if not all_files_found:
        print("❌ No files found in any of the courses.")
        return
    
    print(f"\n✅ Found {len(all_files_found)} files across all courses!")
    
    # Step 5: Demonstrate duplicate detection
    print("\n5️⃣ Checking for existing files (Duplicate Detection Demo)")
    print("🔍 Scanning target folder for existing files...")
    existing_files = []
    for file_info in all_files_found[:3]:  # Check first 3 files as demo
        existing_file = drive_client.file_exists(file_info['title'], target_folder_id)
        if existing_file:
            existing_files.append(file_info['title'])
            print(f"    🔄 '{file_info['title']}' already exists (will be skipped)")
        else:
            print(f"    ✅ '{file_info['title']}' is new (will be uploaded)")
    
    if existing_files:
        print(f"\n💡 Found {len(existing_files)} duplicate(s) that will be automatically skipped!")
    else:
        print(f"\n✨ No duplicates found in sample - all files appear to be new!")
    
    # Step 6: Transfer files
    print(f"\n6️⃣ Transferring Files")
    print("=" * 30)
    print("ℹ️  Files with the same name will be automatically skipped to prevent duplicates!")
    
    successful_transfers = 0
    failed_transfers = 0
    skipped_duplicates = 0
    
    async with aiohttp.ClientSession() as session:
        for i, file_info in enumerate(all_files_found, 1):
            print(f"\n[{i}/{len(all_files_found)}] Processing: {file_info['title']}")
            print(f"    Course: {file_info['course_name']} (ID: {file_info['course_id']})")
            print(f"    Module: {file_info['module_name']}")
            
            try:
                # Download and upload file
                result = await canvas_client.get_file_content(
                    session=session,
                    file_id=file_info['content_id'],
                    folder_id=target_folder_id
                )
                
                if result and result.get('upload_success'):
                    # Check if this was a duplicate (existing file)
                    if result.get('duplicate_skipped', False):
                        skipped_duplicates += 1
                        print(f"    🔄 File already exists - skipped duplicate!")
                        print(f"    📁 Existing file: {result['drive_url']}")
                        print(f"    💾 Saved bandwidth by not re-uploading")
                    else:
                        successful_transfers += 1
                        print(f"    ✅ Successfully uploaded new file!")
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
    print(f"✅ New files uploaded: {successful_transfers}")
    print(f"🔄 Duplicates skipped: {skipped_duplicates}")
    print(f"❌ Failed transfers: {failed_transfers}")
    print(f"📊 Total files processed: {len(all_files_found)}")
    
    # Calculate efficiency metrics
    total_success = successful_transfers + skipped_duplicates
    if len(all_files_found) > 0:
        success_rate = (total_success / len(all_files_found)) * 100
        print(f"📈 Success rate: {success_rate:.1f}%")
        
    if skipped_duplicates > 0:
        print(f"\n💡 Duplicate Detection Benefits:")
        print(f"   • Prevented {skipped_duplicates} redundant uploads")
        print(f"   • Saved bandwidth and storage space")
        print(f"   • Maintained file organization without conflicts")
    
    if successful_transfers > 0 or skipped_duplicates > 0:
        print(f"\n🎉 File transfer process completed successfully!")
        if successful_transfers > 0:
            print(f"   📤 {successful_transfers} new files uploaded")
        if skipped_duplicates > 0:
            print(f"   🔄 {skipped_duplicates} duplicates intelligently skipped")
    
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
import asyncio
import aiohttp
import logging
import mimetypes
from typing import Dict, List, Optional, Any

from config import Config
from drive_client import GoogleDriveClient

class CanvasClient:
    def __init__(self, drive_client: Optional[GoogleDriveClient] = None):
        """Initialize the Canvas API client."""
        self.api_url = Config.CANVAS_URL
        self.api_token = Config.CANVAS_API_TOKEN
        self.headers = {'Authorization': f'Bearer {self.api_token}'}
        self.logger = logging.getLogger(__name__)
        self.drive_client = drive_client

    async def _get(self, session: aiohttp.ClientSession, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make a GET request to the Canvas API."""
        url = f"{self.api_url}{endpoint}"
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                raise Exception(f"API error: {response.status}")
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error fetching {endpoint}: {e}")
            raise

    async def _get_paginated(self, session: aiohttp.ClientSession, endpoint: str) -> List[Dict[str, Any]]:
        """Retrieve all items from a paginated Canvas API endpoint."""
        results = []
        url = f"{self.api_url}{endpoint}"
        while url:
            try:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        raise Exception(f"API error: {response.status}")
                    data = await response.json()
                    results.extend(data if isinstance(data, list) else [data])
                    next_link = response.headers.get('Link', '').split(', ')
                    url = next((link.split(';')[0][1:-1] for link in next_link if 'rel="next"' in link), None)
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error fetching {url}: {e}")
                raise
        return results

    async def get_course(self, course_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a specific course."""
        async with aiohttp.ClientSession() as session:
            return await self._get(session, f"/courses/{course_id}")

    async def get_active_courses(self) -> List[Dict[str, Any]]:
        """Retrieve all active courses for the user."""
        async with aiohttp.ClientSession() as session:
            courses = await self._get_paginated(session, "/courses?enrollment_state=active")
            return [{"id": course["id"], "name": course["name"]} for course in courses or []]

    async def get_course_modules(self, course_id: int) -> List[Dict[str, Any]]:
        """Retrieve all modules for a course."""
        async with aiohttp.ClientSession() as session:
            return await self._get_paginated(session, f"/courses/{course_id}/modules") or []

    async def get_modules(self, session: aiohttp.ClientSession, course_id: int) -> List[Dict[str, Any]]:
        """Retrieve all modules for a course with provided session."""
        return await self._get_paginated(session, f"/courses/{course_id}/modules") or []

    async def get_module_items(self, course_id: int, module_id: int) -> List[Dict[str, Any]]:
        """Retrieve all items in a module."""
        async with aiohttp.ClientSession() as session:
            return await self._get_paginated(session, f"/courses/{course_id}/modules/{module_id}/items") or []

    async def get_module_items_with_session(self, session: aiohttp.ClientSession, course_id: int, module_id: int) -> List[Dict[str, Any]]:
        """Retrieve all items in a module with provided session."""
        return await self._get_paginated(session, f"/courses/{course_id}/modules/{module_id}/items") or []

    async def get_page_content(self, session: aiohttp.ClientSession, course_id: int, page_url: str) -> Optional[str]:
        """Retrieve a course page's content."""
        page = await self._get(session, f"/courses/{course_id}/pages/{page_url}")
        return page.get("body") if page else None

    async def get_quiz_content(self, session: aiohttp.ClientSession, course_id: int, quiz_id: int) -> Optional[str]:
        """Retrieve a quiz's description."""
        quiz = await self._get(session, f"/courses/{course_id}/quizzes/{quiz_id}")
        return quiz.get("description") if quiz else None

    async def get_file_content(self, session: aiohttp.ClientSession, file_id: int, 
                              course_name: Optional[str] = None, 
                              folder_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Download a file and upload it to Google Drive.
        
        Args:
            session: aiohttp session for downloading
            file_id: Canvas file ID
            course_name: Name of the course (for folder organization)
            folder_id: Specific Google Drive folder ID to upload to
            
        Returns:
            dict: File information including Google Drive file ID, or None if failed
        """
        file_info = await self._get(session, f"/files/{file_id}")
        if not file_info:
            self.logger.warning(f"File {file_id} not found in Canvas")
            return None
            
        file_url = file_info.get("url")
        if not file_url:
            self.logger.warning(f"No download URL for file {file_id}")
            return None
            
        filename = file_info.get("display_name", f"canvas_file_{file_id}")
        content_type = file_info.get("content-type", "")
        file_size = file_info.get("size", 0)
        
        try:
            # Download file from Canvas
            self.logger.info(f"Downloading file '{filename}' ({file_size} bytes)")
            async with session.get(file_url) as response:
                if response.status != 200:
                    self.logger.error(f"Failed to download file {file_id}: HTTP {response.status}")
                    return None
                
                file_content = await response.read()
                
                # Determine MIME type if not provided
                if not content_type:
                    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                
                result = {
                    "canvas_file_id": file_id,
                    "filename": filename,
                    "content_type": content_type,
                    "size": len(file_content),
                    "canvas_url": file_url,
                    "drive_file_id": None,
                    "drive_url": None,
                    "upload_success": False
                }
                
                # Upload to Google Drive if drive_client is available
                if self.drive_client:
                    try:
                        # Upload file to Google Drive
                        drive_file_id = self.drive_client.upload_file(
                            file_content=file_content,
                            filename=filename,
                            mime_type=content_type,
                            folder_id=folder_id
                        )
                        
                        if drive_file_id:
                            result.update({
                                "drive_file_id": drive_file_id,
                                "drive_url": f"https://drive.google.com/file/d/{drive_file_id}/view",
                                "upload_success": True
                            })
                            self.logger.info(f"Successfully uploaded '{filename}' to Google Drive")
                        else:
                            self.logger.error(f"Failed to upload '{filename}' to Google Drive")
                            
                    except Exception as e:
                        self.logger.error(f"Error uploading file to Google Drive: {e}")
                        
                else:
                    self.logger.info(f"No Google Drive client available, file downloaded but not uploaded")
                
                return result
                
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error downloading file {file_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error processing file {file_id}: {e}")
            return None

    async def fetch_module_item_content(self, session: aiohttp.ClientSession, course_id: int, 
                                       module_item: Dict[str, Any], course_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Fetch content of a module item based on its type.
        
        Args:
            session: aiohttp session
            course_id: Canvas course ID
            module_item: Module item data from Canvas
            course_name: Name of the course (for file organization)
            
        Returns:
            dict: Content information (varies by item type)
        """
        item_type = module_item.get("type")
        
        if item_type == "Page":
            content = await self.get_page_content(session, course_id, module_item.get("page_url", ""))
            return {
                "type": "page",
                "content": content,
                "title": module_item.get("title"),
                "page_url": module_item.get("page_url")
            }
        elif item_type == "File":
            file_result = await self.get_file_content(
                session, 
                module_item.get("content_id", 0), 
                course_name=course_name
            )
            if file_result:
                file_result["type"] = "file"
                file_result["title"] = module_item.get("title")
            return file_result
        else:
            return {
                "type": item_type.lower() if item_type else "unknown",
                "title": module_item.get("title"),
                "url": module_item.get("html_url"),
                "content": f"Unsupported item type: {item_type}"
            }

    def _html_to_text(self, html_content: Optional[str]) -> str:
        """Convert HTML to plain text."""
        if not html_content:
            return ""
        try:
            from bs4 import BeautifulSoup
            return ' '.join(BeautifulSoup(html_content, 'html.parser').get_text(separator=' ', strip=True).split())
        except ImportError:
            self.logger.warning("BeautifulSoup not available")
            return html_content
        except Exception as e:
            self.logger.error(f"HTML conversion error: {e}")
            return html_content or ""

    async def get_assignments(self, session: aiohttp.ClientSession, course_id: int) -> List[Dict[str, Any]]:
        """Retrieve all assignments for a course."""
        assignments = await self._get_paginated(session, f"/courses/{course_id}/assignments") or []
        return [
            {
                "name": a.get("name", "Unnamed Assignment"),
                "due_at": a.get("due_at"),
                "type": "assignment",
                "description": self._html_to_text(a.get("description"))
            } for a in assignments
        ]

    async def get_quizzes(self, session: aiohttp.ClientSession, course_id: int) -> List[Dict[str, Any]]:
        """Retrieve all quizzes for a course."""
        quizzes = await self._get_paginated(session, f"/courses/{course_id}/quizzes") or []
        return [
            {
                "name": q.get("title", "Unnamed Quiz"),
                "due_at": q.get("due_at"),
                "type": "quiz",
                "description": self._html_to_text(q.get("description"))
            } for q in quizzes
        ]

async def main():
    """Run the Canvas client to fetch data."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    client = CanvasClient()
    course_id = 213007
    async with aiohttp.ClientSession() as session:
        try:
            assignments = await client.get_assignments(session, course_id)
            print(f"Assignments ({len(assignments)}):")
            for a in assignments:
                print(f"  - {a['name']} (Due: {a['due_at']})")
                if a['description']:
                    print(f"    Description: {a['description'][:100]}...")

            quizzes = await client.get_quizzes(session, course_id)
            print(f"Quizzes ({len(quizzes)}):")
            for q in quizzes:
                print(f"  - {q['name']} (Due: {q['due_at']})")
                if q['description']:
                    print(f"    Description: {q['description'][:100]}...")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
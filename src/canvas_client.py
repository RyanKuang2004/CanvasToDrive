import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional, Any

from config import Config

class CanvasClient:
    def __init__(self):
        """Initialize the Canvas API client."""
        self.api_url = Config.CANVAS_URL
        self.api_token = Config.CANVAS_API_TOKEN
        self.headers = {'Authorization': f'Bearer {self.api_token}'}
        self.logger = logging.getLogger(__name__)

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

    async def get_file_content(self, session: aiohttp.ClientSession, file_id: int) -> Optional[str]:
        """Retrieve a file's content."""
        file_info = await self._get(session, f"/files/{file_id}")
        if file_info and (url := file_info.get("url")):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        content_type = file_info.get("content-type", "").lower()
                        if content_type.startswith("text/") or "html" in content_type:
                            return await response.text()
                        return f"Binary file: {file_info.get('display_name', 'Unknown')} ({content_type})"
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error downloading file {file_id}: {e}")
        return None

    async def fetch_module_item_content(self, session: aiohttp.ClientSession, course_id: int, module_item: Dict[str, Any]) -> Optional[str]:
        """Fetch content of a module item based on its type."""
        item_type = module_item.get("type")
        if item_type == "Page":
            return await self.get_page_content(session, course_id, module_item.get("page_url", ""))
        elif item_type == "File":
            return await self.get_file_content(session, module_item.get("content_id", 0))
        return None

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
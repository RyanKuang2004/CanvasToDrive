import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Union, Any

import aiohttp

from config import Config

class CanvasClient:
    def __init__(self, session: Optional[aiohttp.ClientSession] = None):
        """Initialize the Canvas API client with configuration.
        
        Args:
            session: Optional aiohttp session. If None, client will manage its own session.
        """
        self.api_url = Config.CANVAS_URL
        self.api_token = Config.CANVAS_API_TOKEN
        self.headers = {'Authorization': f'Bearer {self.api_token}'}
        self._session = session
        self._should_close_session = session is None

    @asynccontextmanager
    async def _get_session(self):
        """Get or create an aiohttp session."""
        if self._session:
            yield self._session
        else:
            async with aiohttp.ClientSession() as session:
                yield session
    
    async def _get(self, session: aiohttp.ClientSession, endpoint: str) -> Optional[Dict[str, Any]]:
        """Make a GET request to the Canvas API.
        
        Args:
            session: The active client session
            endpoint: The API endpoint to request
            
        Returns:
            The JSON response data if successful, None if 404
            
        Raises:
            CanvasAPIError: For API errors other than 404
        """
        url = f"{self.api_url}{endpoint}"
        self.logger.debug(f"Making GET request to: {url}")
        
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    data = await response.json()
                    self.logger.debug(f"Successfully fetched {endpoint}")
                    return data
                elif response.status == 404:
                    self.logger.info(f"Resource not found: {endpoint}")
                    return None
                else:
                    error_msg = f"Failed to fetch {endpoint}: {response.status}"
                    self.logger.error(error_msg)
                    raise CanvasAPIError(error_msg, response.status, endpoint)
        except aiohttp.ClientError as e:
            error_msg = f"Network error fetching {endpoint}: {str(e)}"
            self.logger.error(error_msg)
            raise CanvasAPIError(error_msg, 0, endpoint)
            
    async def _get_paginated(self, session: aiohttp.ClientSession, endpoint: str) -> List[Dict[str, Any]]:
        """
        Retrieves all items from a paginated Canvas API endpoint.

        Args:
            session: The active aiohttp client session.
            endpoint: The initial API endpoint to request.

        Returns:
            A list containing all items from all pages.
        """
        all_results = []
        url = f"{self.api_url}{endpoint}"

        while url:
            self.logger.debug(f"Fetching paginated data from: {url}")
            try:
                async with session.get(url, headers=self.headers) as response:
                    if response.status != 200:
                        error_msg = f"Failed to fetch paginated data from {url}: {response.status}"
                        self.logger.error(error_msg)
                        raise CanvasAPIError(error_msg, response.status, url)

                    data = await response.json()
                    if isinstance(data, list):
                        all_results.extend(data)
                    else:
                        # Handle cases where a non-list is returned unexpectedly
                        self.logger.warning(f"Expected a list from {url}, but got {type(data)}. Stopping pagination.")
                        if not all_results: # If this was the first and only page
                            return data
                        break

                    # Find the 'next' link in the Link header
                    next_link = None
                    link_header = response.headers.get('Link')
                    if link_header:
                        links = link_header.split(',')
                        for link in links:
                            parts = link.split(';')
                            if len(parts) == 2 and parts[1].strip() == 'rel="next"':
                                # Extract URL from <...>
                                next_link = parts[0].strip()[1:-1]
                                break
                    url = next_link # Continue loop with the next URL, or exit if None
            
            except aiohttp.ClientError as e:
                error_msg = f"Network error fetching paginated data from {url}: {str(e)}"
                self.logger.error(error_msg)
                raise CanvasAPIError(error_msg, 0, url)

        self.logger.info(f"Fetched a total of {len(all_results)} items from endpoint: {endpoint}")
        return all_results

    async def get_course(self, course_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve information about a specific course.
        
        Args:
            course_id: The Canvas course ID
            
        Returns:
            A dictionary containing course information if successful, None otherwise
        """
        async with self._get_session() as session:
            return await self._get(session, f"/courses/{course_id}")
    
    async def get_active_courses(self) -> List[Dict[str, Union[int, str]]]:
        """Retrieve all active courses for the authenticated user by handling pagination.
        
        This method is now more efficient by using the `enrollment_state=active` 
        parameter to filter courses on the server side.
        
        Returns:
            A list of dictionaries containing course information.
        """
        async with self._get_session() as session:
            # Use the paginated helper and the efficient 'enrollment_state' parameter
            active_courses = await self._get_paginated(session, "/courses?enrollment_state=active")
            
            if not active_courses:
                return []
            
            # The API now only returns active courses, so no client-side filtering is needed.
            return [
                {"id": course["id"], "name": course["name"]} 
                for course in active_courses
            ]

    async def get_course_modules(self, course_id: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve all modules for a course.
        
        Args:
            course_id: The Canvas course ID
            
        Returns:
            A list of module dictionaries or None if not found
        """
        async with self._get_session() as session:
            return await self._get_paginated(session, f"/courses/{course_id}/modules")
    
    async def get_modules(self, session: aiohttp.ClientSession, course_id: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve all modules for a course.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            
        Returns:
            A list of module dictionaries or None if not found
        """
        # Note: This endpoint is also paginated. For full functionality, it should also use _get_paginated.
        return await self._get_paginated(session, f"/courses/{course_id}/modules")

    async def get_module_items(self, course_id: int, module_id: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve all items within a module.
        
        Args:
            course_id: The Canvas course ID
            module_id: The Canvas module ID
            
        Returns:
            A list of module item dictionaries or None if not found
        """
        async with self._get_session() as session:
            return await self._get_paginated(session, f"/courses/{course_id}/modules/{module_id}/items")

    async def get_module_items_with_session(self, session: aiohttp.ClientSession, course_id: int, module_id: int) -> Optional[List[Dict[str, Any]]]:
        """Retrieve all items within a module.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            module_id: The Canvas module ID
            
        Returns:
            A list of module item dictionaries or None if not found
        """
        # Note: This endpoint is also paginated. For full functionality, it should also use _get_paginated.
        return await self._get_paginated(session, f"/courses/{course_id}/modules/{module_id}/items")

    async def get_page_content(self, session: aiohttp.ClientSession, course_id: int, page_url: str) -> Optional[str]:
        """Retrieve the content of a course page.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            page_url: The page URL identifier
            
        Returns:
            The page content if successful, None otherwise
        """
        page = await self._get(session, f"/courses/{course_id}/pages/{page_url}")
        return page.get("body") if page else None

    async def get_quiz_content(self, session: aiohttp.ClientSession, course_id: int, quiz_id: int) -> Optional[str]:
        """Retrieve the content of a quiz.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            quiz_id: The Canvas quiz ID
            
        Returns:
            The quiz description if successful, None otherwise
        """
        quiz = await self._get(session, f"/courses/{course_id}/quizzes/{quiz_id}")
        return quiz.get("description") if quiz else None

    async def get_file_content(self, session: aiohttp.ClientSession, file_id: int) -> Optional[str]:
        """Retrieve the content of a file.
        
        Args:
            session: The active client session
            file_id: The Canvas file ID
            
        Returns:
            The file content if successful, None otherwise
        """
        file_info = await self._get(session, f"/files/{file_id}")
        if file_info and (download_url := file_info.get("url")):
            try:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        # Get content type to determine how to handle the file
                        content_type = file_info.get("content-type", "").lower()
                        
                        if content_type.startswith("text/") or "html" in content_type:
                            # Text files can be decoded as UTF-8
                            content = await response.text()
                            self.logger.debug(f"Successfully retrieved text content for file {file_id}")
                            return content
                        else:
                            # Binary files (PDF, PPTX, etc.) - return metadata for now
                            file_size = len(await response.read())
                            filename = file_info.get("display_name", "Unknown")
                            content_summary = f"Binary file: {filename} ({content_type}, {file_size} bytes)"
                            self.logger.debug(f"Retrieved binary file info for file {file_id}: {content_summary}")
                            return content_summary
                    else:
                        self.logger.warning(f"Failed to download file {file_id}: {response.status}")
            except aiohttp.ClientError as e:
                self.logger.error(f"Network error downloading file {file_id}: {str(e)}")
            except UnicodeDecodeError as e:
                # Handle files that look like text but have encoding issues
                self.logger.warning(f"Encoding error for file {file_id}: {str(e)}")
                filename = file_info.get("display_name", "Unknown")
                return f"File with encoding issues: {filename}"
        return None

    async def fetch_module_item_content(self, session: aiohttp.ClientSession, course_id: int, module_item: Dict[str, Any]) -> Optional[str]:
        """Fetch the content of a module item based on its type.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            module_item: The module item information
            
        Returns:
            The content of the module item if available, None otherwise
        """
        item_type = module_item.get("type")
        
        if item_type == "Page":
            page_url = module_item.get("page_url")
            if page_url:
                return await self.get_page_content(session, course_id, page_url)
        elif item_type == "File":
            content_id = module_item.get("content_id")
            if content_id:
                return await self.get_file_content(session, content_id)
        
        self.logger.debug(f"Unsupported or missing content for item type: {item_type}")
        return None

    def _html_to_text(self, html_content: Optional[str]) -> str:
        """Convert HTML content to plain text.
        
        Args:
            html_content: HTML string to convert
            
        Returns:
            Plain text string, empty string if None
        """
        if not html_content:
            return ""
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            # Get text and clean up whitespace
            text = soup.get_text(separator=' ', strip=True)
            return ' '.join(text.split())  # Normalize whitespace
        except ImportError:
            self.logger.warning("BeautifulSoup not available, returning raw HTML")
            return html_content
        except Exception as e:
            self.logger.error(f"Error converting HTML to text: {e}")
            return html_content or ""

    async def get_assignments(self, session: aiohttp.ClientSession, course_id: int) -> List[Dict[str, Any]]:
        """Retrieve all assignments for a course.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            
        Returns:
            List of assignment dictionaries with name, due_at, type, and description
        """
        try:
            assignments = await self._get_paginated(session, f"/courses/{course_id}/assignments")
            if not assignments:
                self.logger.info(f"No assignments found for course {course_id}")
                return []
            
            assignment_data = []
            for assignment in assignments:
                assignment_info = {
                    'name': assignment.get('name', 'Unnamed Assignment'),
                    'due_at': assignment.get('due_at'),
                    'type': 'assignment',
                    'description': self._html_to_text(assignment.get('description'))
                }
                assignment_data.append(assignment_info)
            
            self.logger.info(f"Fetched {len(assignment_data)} assignments for course {course_id}")
            return assignment_data
            
        except CanvasAPIError as e:
            self.logger.error(f"Error fetching assignments for course {course_id}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching assignments for course {course_id}: {str(e)}")
            raise

    async def get_quizzes(self, session: aiohttp.ClientSession, course_id: int) -> List[Dict[str, Any]]:
        """Retrieve all quizzes for a course.
        
        Args:
            session: The active client session
            course_id: The Canvas course ID
            
        Returns:
            List of quiz dictionaries with name, due_at, type, and description
        """
        try:
            quizzes = await self._get_paginated(session, f"/courses/{course_id}/quizzes")
            if not quizzes:
                self.logger.info(f"No quizzes found for course {course_id}")
                return []
            
            quiz_data = []
            for quiz in quizzes:
                quiz_info = {
                    'name': quiz.get('title', 'Unnamed Quiz'),
                    'due_at': quiz.get('due_at'),
                    'type': 'quiz',
                    'description': self._html_to_text(quiz.get('description'))
                }
                quiz_data.append(quiz_info)
            
            self.logger.info(f"Fetched {len(quiz_data)} quizzes for course {course_id}")
            return quiz_data
            
        except CanvasAPIError as e:
            self.logger.error(f"Error fetching quizzes for course {course_id}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error fetching quizzes for course {course_id}: {str(e)}")
            raise
    
def main() -> None:
    """Main function to run the Canvas client and fetch data."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    client = CanvasClient()
    
    async def run() -> None:
        """Run the Canvas data fetching process."""
        async with aiohttp.ClientSession() as session:
            try:
                # Test new assignment and quiz functions
                course_id = 213007  # Statistical Learning course
                
                assignments = await client.get_assignments(session, course_id)
                print(f"Assignments ({len(assignments)}):")
                for assignment in assignments:
                    print(f"  - {assignment['name']} (Due: {assignment['due_at']})")
                    if assignment['description']:
                        print(f"    Description: {assignment['description'][:100]}...")
                
                quizzes = await client.get_quizzes(session, course_id)
                print(f"\nQuizzes ({len(quizzes)}):")
                for quiz in quizzes:
                    print(f"  - {quiz['name']} (Due: {quiz['due_at']})")
                    if quiz['description']:
                        print(f"    Description: {quiz['description'][:100]}...")
                
                # Alternative demo code for full course processing can be added here if needed
                        
            except CanvasClientError as e:
                print(f"Canvas client error: {e}")
            except Exception as e:
                print(f"Unexpected error: {e}")
                raise

    asyncio.run(run())

if __name__ == "__main__":
    main()
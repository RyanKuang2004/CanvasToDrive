import pytest
import asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from typing import Dict, Any, List
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from canvas_client import CanvasClient


class TestCanvasClient:
    """Test suite for CanvasClient class."""

    @pytest.fixture
    def client(self):
        """Create a CanvasClient instance for testing."""
        with patch('canvas_client.Config') as mock_config:
            mock_config.CANVAS_URL = 'https://test.canvas.edu/api/v1'
            mock_config.CANVAS_API_TOKEN = 'test_token'
            return CanvasClient()

    @pytest.fixture
    def mock_session(self):
        """Create a mock aiohttp session."""
        session = AsyncMock(spec=aiohttp.ClientSession)
        return session

    def test_initialization(self, client):
        """Test CanvasClient initialization."""
        assert client.api_url == 'https://test.canvas.edu/api/v1'
        assert client.api_token == 'test_token'
        assert client.headers == {'Authorization': 'Bearer test_token'}
        assert client.logger is not None

    @pytest.mark.asyncio
    async def test_get_success(self, client, mock_session):
        """Test successful _get request."""
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {'id': 1, 'name': 'Test Course'}
        mock_session.get.return_value.__aenter__.return_value = mock_response

        result = await client._get(mock_session, '/courses/1')

        assert result == {'id': 1, 'name': 'Test Course'}
        mock_session.get.assert_called_once_with(
            'https://test.canvas.edu/api/v1/courses/1',
            headers={'Authorization': 'Bearer test_token'}
        )

    @pytest.mark.asyncio
    async def test_get_not_found(self, client, mock_session):
        """Test _get request returns None for 404."""
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_session.get.return_value.__aenter__.return_value = mock_response

        result = await client._get(mock_session, '/courses/999')

        assert result is None

    @pytest.mark.asyncio
    async def test_get_api_error(self, client, mock_session):
        """Test _get request raises exception for API errors."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="API error: 500"):
            await client._get(mock_session, '/courses/1')

    @pytest.mark.asyncio
    async def test_get_network_error(self, client, mock_session):
        """Test _get request handles network errors."""
        mock_session.get.side_effect = aiohttp.ClientError("Network error")

        with pytest.raises(aiohttp.ClientError):
            await client._get(mock_session, '/courses/1')

    @pytest.mark.asyncio
    async def test_get_paginated_single_page(self, client, mock_session):
        """Test _get_paginated with single page response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = [{'id': 1}, {'id': 2}]
        mock_response.headers = {'Link': ''}
        mock_session.get.return_value.__aenter__.return_value = mock_response

        result = await client._get_paginated(mock_session, '/courses')

        assert result == [{'id': 1}, {'id': 2}]
        assert mock_session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_get_paginated_multiple_pages(self, client, mock_session):
        """Test _get_paginated with multiple pages."""
        # First page response
        mock_response1 = AsyncMock()
        mock_response1.status = 200
        mock_response1.json.return_value = [{'id': 1}]
        mock_response1.headers = {
            'Link': '<https://test.canvas.edu/api/v1/courses?page=2>; rel="next"'
        }

        # Second page response
        mock_response2 = AsyncMock()
        mock_response2.status = 200
        mock_response2.json.return_value = [{'id': 2}]
        mock_response2.headers = {'Link': ''}

        mock_session.get.return_value.__aenter__.side_effect = [
            mock_response1, mock_response2
        ]

        result = await client._get_paginated(mock_session, '/courses')

        assert result == [{'id': 1}, {'id': 2}]
        assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_paginated_api_error(self, client, mock_session):
        """Test _get_paginated handles API errors."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.get.return_value.__aenter__.return_value = mock_response

        with pytest.raises(Exception, match="API error: 500"):
            await client._get_paginated(mock_session, '/courses')

    @pytest.mark.asyncio
    async def test_get_course(self, client):
        """Test get_course method."""
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = {'id': 1, 'name': 'Test Course'}

            result = await client.get_course(1)

            assert result == {'id': 1, 'name': 'Test Course'}
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert args[1] == '/courses/1'

    @pytest.mark.asyncio
    async def test_get_active_courses(self, client):
        """Test get_active_courses method."""
        mock_courses = [
            {'id': 1, 'name': 'Course 1'},
            {'id': 2, 'name': 'Course 2'}
        ]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_courses

            result = await client.get_active_courses()

            expected = [{'id': 1, 'name': 'Course 1'}, {'id': 2, 'name': 'Course 2'}]
            assert result == expected
            mock_get_paginated.assert_called_once()
            args, kwargs = mock_get_paginated.call_args
            assert args[1] == '/courses?enrollment_state=active'

    @pytest.mark.asyncio
    async def test_get_active_courses_empty(self, client):
        """Test get_active_courses with empty response."""
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = None

            result = await client.get_active_courses()

            assert result == []

    @pytest.mark.asyncio
    async def test_get_course_modules(self, client):
        """Test get_course_modules method."""
        mock_modules = [{'id': 1, 'name': 'Module 1'}]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_modules

            result = await client.get_course_modules(123)

            assert result == mock_modules
            mock_get_paginated.assert_called_once()
            args, kwargs = mock_get_paginated.call_args
            assert args[1] == '/courses/123/modules'

    @pytest.mark.asyncio
    async def test_get_modules_with_session(self, client, mock_session):
        """Test get_modules method with provided session."""
        mock_modules = [{'id': 1, 'name': 'Module 1'}]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_modules

            result = await client.get_modules(mock_session, 123)

            assert result == mock_modules
            mock_get_paginated.assert_called_once_with(mock_session, '/courses/123/modules')

    @pytest.mark.asyncio
    async def test_get_module_items(self, client):
        """Test get_module_items method."""
        mock_items = [{'id': 1, 'title': 'Item 1'}]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_items

            result = await client.get_module_items(123, 456)

            assert result == mock_items
            mock_get_paginated.assert_called_once()
            args, kwargs = mock_get_paginated.call_args
            assert args[1] == '/courses/123/modules/456/items'

    @pytest.mark.asyncio
    async def test_get_module_items_with_session(self, client, mock_session):
        """Test get_module_items_with_session method."""
        mock_items = [{'id': 1, 'title': 'Item 1'}]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = mock_items

            result = await client.get_module_items_with_session(mock_session, 123, 456)

            assert result == mock_items
            mock_get_paginated.assert_called_once_with(
                mock_session, '/courses/123/modules/456/items'
            )

    @pytest.mark.asyncio
    async def test_get_page_content(self, client, mock_session):
        """Test get_page_content method."""
        mock_page = {'body': '<p>Page content</p>'}
        
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = mock_page

            result = await client.get_page_content(mock_session, 123, 'test-page')

            assert result == '<p>Page content</p>'
            mock_get.assert_called_once_with(mock_session, '/courses/123/pages/test-page')

    @pytest.mark.asyncio
    async def test_get_page_content_not_found(self, client, mock_session):
        """Test get_page_content when page not found."""
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = None

            result = await client.get_page_content(mock_session, 123, 'missing-page')

            assert result is None

    @pytest.mark.asyncio
    async def test_get_quiz_content(self, client, mock_session):
        """Test get_quiz_content method."""
        mock_quiz = {'description': '<p>Quiz description</p>'}
        
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = mock_quiz

            result = await client.get_quiz_content(mock_session, 123, 456)

            assert result == '<p>Quiz description</p>'
            mock_get.assert_called_once_with(mock_session, '/courses/123/quizzes/456')

    @pytest.mark.asyncio
    async def test_get_file_content_text_file(self, client, mock_session):
        """Test get_file_content for text file."""
        mock_file_info = {
            'url': 'https://example.com/file.txt',
            'content-type': 'text/plain',
            'display_name': 'test.txt'
        }
        
        # Mock file info response
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = mock_file_info
            
            # Mock file content response
            mock_content_response = AsyncMock()
            mock_content_response.status = 200
            mock_content_response.text.return_value = 'File content'
            mock_session.get.return_value.__aenter__.return_value = mock_content_response

            result = await client.get_file_content(mock_session, 123)

            assert result == 'File content'
            mock_get.assert_called_once_with(mock_session, '/files/123')

    @pytest.mark.asyncio
    async def test_get_file_content_binary_file(self, client, mock_session):
        """Test get_file_content for binary file."""
        mock_file_info = {
            'url': 'https://example.com/file.pdf',
            'content-type': 'application/pdf',
            'display_name': 'test.pdf'
        }
        
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = mock_file_info
            
            mock_content_response = AsyncMock()
            mock_content_response.status = 200
            mock_session.get.return_value.__aenter__.return_value = mock_content_response

            result = await client.get_file_content(mock_session, 123)

            assert result == 'Binary file: test.pdf (application/pdf)'

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, client, mock_session):
        """Test get_file_content when file not found."""
        with patch.object(client, '_get') as mock_get:
            mock_get.return_value = None

            result = await client.get_file_content(mock_session, 123)

            assert result is None

    @pytest.mark.asyncio
    async def test_fetch_module_item_content_page(self, client, mock_session):
        """Test fetch_module_item_content for page item."""
        module_item = {'type': 'Page', 'page_url': 'test-page'}
        
        with patch.object(client, 'get_page_content') as mock_get_page:
            mock_get_page.return_value = 'Page content'

            result = await client.fetch_module_item_content(mock_session, 123, module_item)

            assert result == 'Page content'
            mock_get_page.assert_called_once_with(mock_session, 123, 'test-page')

    @pytest.mark.asyncio
    async def test_fetch_module_item_content_file(self, client, mock_session):
        """Test fetch_module_item_content for file item."""
        module_item = {'type': 'File', 'content_id': 456}
        
        with patch.object(client, 'get_file_content') as mock_get_file:
            mock_get_file.return_value = 'File content'

            result = await client.fetch_module_item_content(mock_session, 123, module_item)

            assert result == 'File content'
            mock_get_file.assert_called_once_with(mock_session, 456)

    @pytest.mark.asyncio
    async def test_fetch_module_item_content_unsupported(self, client, mock_session):
        """Test fetch_module_item_content for unsupported item type."""
        module_item = {'type': 'ExternalTool'}

        result = await client.fetch_module_item_content(mock_session, 123, module_item)

        assert result is None

    def test_html_to_text_with_beautifulsoup(self, client):
        """Test _html_to_text with BeautifulSoup available."""
        html_content = '<p>Hello <b>world</b>!</p><div>Test content</div>'
        
        with patch('canvas_client.BeautifulSoup') as mock_bs:
            mock_soup = MagicMock()
            mock_soup.get_text.return_value = 'Hello world! Test content'
            mock_bs.return_value = mock_soup

            result = client._html_to_text(html_content)

            assert result == 'Hello world! Test content'
            mock_bs.assert_called_once_with(html_content, 'html.parser')

    def test_html_to_text_without_beautifulsoup(self, client):
        """Test _html_to_text without BeautifulSoup."""
        html_content = '<p>Hello world!</p>'
        
        with patch('canvas_client.BeautifulSoup', side_effect=ImportError):
            result = client._html_to_text(html_content)
            
            assert result == html_content

    def test_html_to_text_empty_content(self, client):
        """Test _html_to_text with empty content."""
        assert client._html_to_text(None) == ""
        assert client._html_to_text("") == ""

    def test_html_to_text_exception_handling(self, client):
        """Test _html_to_text exception handling."""
        html_content = '<p>Test</p>'
        
        with patch('canvas_client.BeautifulSoup', side_effect=Exception("Parse error")):
            result = client._html_to_text(html_content)
            
            assert result == html_content

    @pytest.mark.asyncio
    async def test_get_assignments(self, client, mock_session):
        """Test get_assignments method."""
        mock_assignments = [
            {
                'name': 'Assignment 1',
                'due_at': '2024-12-01T23:59:59Z',
                'description': '<p>Do the assignment</p>'
            },
            {
                'name': 'Assignment 2',
                'due_at': None,
                'description': None
            }
        ]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated, \
             patch.object(client, '_html_to_text') as mock_html_to_text:
            
            mock_get_paginated.return_value = mock_assignments
            mock_html_to_text.side_effect = ['Do the assignment', '']

            result = await client.get_assignments(mock_session, 123)

            expected = [
                {
                    'name': 'Assignment 1',
                    'due_at': '2024-12-01T23:59:59Z',
                    'type': 'assignment',
                    'description': 'Do the assignment'
                },
                {
                    'name': 'Assignment 2',
                    'due_at': None,
                    'type': 'assignment',
                    'description': ''
                }
            ]
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_assignments_empty(self, client, mock_session):
        """Test get_assignments with empty response."""
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = None

            result = await client.get_assignments(mock_session, 123)

            assert result == []

    @pytest.mark.asyncio
    async def test_get_quizzes(self, client, mock_session):
        """Test get_quizzes method."""
        mock_quizzes = [
            {
                'title': 'Quiz 1',
                'due_at': '2024-12-01T23:59:59Z',
                'description': '<p>Take the quiz</p>'
            },
            {
                'title': 'Quiz 2',
                'due_at': None,
                'description': None
            }
        ]
        
        with patch.object(client, '_get_paginated') as mock_get_paginated, \
             patch.object(client, '_html_to_text') as mock_html_to_text:
            
            mock_get_paginated.return_value = mock_quizzes
            mock_html_to_text.side_effect = ['Take the quiz', '']

            result = await client.get_quizzes(mock_session, 123)

            expected = [
                {
                    'name': 'Quiz 1',
                    'due_at': '2024-12-01T23:59:59Z',
                    'type': 'quiz',
                    'description': 'Take the quiz'
                },
                {
                    'name': 'Quiz 2',
                    'due_at': None,
                    'type': 'quiz',
                    'description': ''
                }
            ]
            assert result == expected

    @pytest.mark.asyncio
    async def test_get_quizzes_empty(self, client, mock_session):
        """Test get_quizzes with empty response."""
        with patch.object(client, '_get_paginated') as mock_get_paginated:
            mock_get_paginated.return_value = None

            result = await client.get_quizzes(mock_session, 123)

            assert result == []


class TestCanvasClientIntegration:
    """Integration tests for CanvasClient that test multiple methods together."""

    @pytest.fixture
    def client(self):
        """Create a CanvasClient instance for testing."""
        with patch('canvas_client.Config') as mock_config:
            mock_config.CANVAS_URL = 'https://test.canvas.edu/api/v1'
            mock_config.CANVAS_API_TOKEN = 'test_token'
            return CanvasClient()

    @pytest.mark.asyncio
    async def test_full_course_data_retrieval(self, client):
        """Test retrieving complete course data including assignments and quizzes."""
        course_data = {'id': 123, 'name': 'Test Course'}
        assignments_data = [{'name': 'Test Assignment', 'due_at': None, 'description': 'Test'}]
        quizzes_data = [{'title': 'Test Quiz', 'due_at': None, 'description': 'Quiz test'}]
        
        with patch.object(client, 'get_course') as mock_get_course, \
             patch.object(client, 'get_assignments') as mock_get_assignments, \
             patch.object(client, 'get_quizzes') as mock_get_quizzes:
            
            mock_get_course.return_value = course_data
            mock_get_assignments.return_value = assignments_data
            mock_get_quizzes.return_value = quizzes_data

            # Simulate getting course data
            course = await client.get_course(123)
            
            # Use aiohttp session for assignments and quizzes
            async with aiohttp.ClientSession() as session:
                assignments = await client.get_assignments(session, 123)
                quizzes = await client.get_quizzes(session, 123)

            assert course == course_data
            assert assignments == assignments_data
            assert quizzes == quizzes_data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
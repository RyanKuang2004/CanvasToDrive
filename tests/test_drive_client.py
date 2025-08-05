"""
Tests for GoogleDriveClient class
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drive_client import GoogleDriveClient


class TestGoogleDriveClient:
    """Test cases for GoogleDriveClient"""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock GoogleDriveClient with authenticated service"""
        client = GoogleDriveClient()
        client.service = Mock()
        client.credentials = Mock()
        return client
    
    def test_file_exists_method_exists(self, mock_client):
        """Test that file_exists method exists - SHOULD FAIL initially"""
        assert hasattr(mock_client, 'file_exists'), "file_exists method should exist"
    
    def test_file_exists_returns_file_info_when_file_found(self, mock_client):
        """Test file_exists returns file info when file is found in folder"""
        # Mock service response with existing file
        mock_client.service.files().list().execute.return_value = {
            'files': [{'id': 'file123', 'name': 'test.pdf'}]
        }
        
        result = mock_client.file_exists('test.pdf', 'folder123')
        assert result == {'id': 'file123', 'name': 'test.pdf'}, "Should return file info when file exists"
    
    def test_file_exists_returns_none_when_file_not_found(self, mock_client):
        """Test file_exists returns None when file not found"""
        # Mock service response with no files
        mock_client.service.files().list().execute.return_value = {
            'files': []
        }
        
        result = mock_client.file_exists('nonexistent.pdf', 'folder123')
        assert result is None, "Should return None when file doesn't exist"
    
    def test_file_exists_with_no_folder_searches_root(self, mock_client):
        """Test file_exists searches in root when no folder_id provided - SHOULD FAIL initially"""
        mock_client.service.files().list().execute.return_value = {
            'files': []
        }
        
        mock_client.file_exists('test.pdf')
        
        # Verify the query doesn't include parent folder constraint
        args, kwargs = mock_client.service.files().list.call_args
        query = kwargs.get('q', '')
        assert 'parents' not in query, "Should not search in specific parent when folder_id is None"
    
    def test_upload_file_skips_when_file_exists(self, mock_client):
        """Test upload_file skips upload when file already exists - SHOULD FAIL initially"""
        # Mock file_exists to return existing file info
        existing_file_info = {'id': 'existing_file_123', 'name': 'test.pdf'}
        mock_client.file_exists = Mock(return_value=existing_file_info)
        
        result = mock_client.upload_file(
            filename='test.pdf',
            mime_type='application/pdf',
            file_content=b'test content',
            folder_id='folder123'
        )
        
        # Should return existing file ID
        assert result == 'existing_file_123', "Should return existing file ID when file exists"
        # Verify upload was not called
        mock_client.service.files().create.assert_not_called()
    
    def test_upload_file_proceeds_when_file_not_exists(self, mock_client):
        """Test upload_file proceeds with upload when file doesn't exist"""
        # Reset mock to clean state
        mock_client.service.reset_mock()
        
        # Mock file_exists to return None (file doesn't exist)
        mock_client.file_exists = Mock(return_value=None)
        
        # Setup mock for the upload flow
        mock_request = Mock()
        mock_request.execute.return_value = {'id': 'new_file_123'}
        mock_client.service.files().create.return_value = mock_request
        
        result = mock_client.upload_file(
            filename='new_test.pdf',
            mime_type='application/pdf',
            file_content=b'test content',
            folder_id='folder123'
        )
        
        assert result == 'new_file_123', "Should return new file ID"
        # Verify upload was called 
        mock_client.service.files().create.assert_called_once()
    
    def test_upload_file_returns_existing_file_info_when_duplicate(self, mock_client):
        """Test upload_file returns existing file info when duplicate found - SHOULD FAIL initially"""
        # Mock file_exists to return existing file info
        existing_file_info = {'id': 'existing123', 'name': 'test.pdf'}
        mock_client.file_exists = Mock(return_value=existing_file_info)
        
        result = mock_client.upload_file(
            filename='test.pdf',
            mime_type='application/pdf',
            file_content=b'test content',
            folder_id='folder123'
        )
        
        # Should return existing file info or ID
        assert result is not None, "Should return existing file info"
        # Verify upload was not called
        mock_client.service.files().create.assert_not_called()
    
    @patch('builtins.open', create=True)
    @patch('drive_client.Path')
    def test_upload_file_with_file_path_checks_for_duplicates(self, mock_path, mock_open, mock_client):
        """Test upload_file checks for duplicates when uploading from file path"""
        # Reset mock to clean state
        mock_client.service.reset_mock()
        
        # Mock Path.is_file to return True
        mock_path.return_value.is_file.return_value = True
        
        # Mock open to return a fake file object
        mock_file = Mock()
        mock_open.return_value = mock_file
        
        # Mock file_exists to return None (no duplicate)
        mock_client.file_exists = Mock(return_value=None)
        
        # Setup mock for the upload flow
        mock_request = Mock()
        mock_request.execute.return_value = {'id': 'new_file_456'}
        mock_client.service.files().create.return_value = mock_request
        
        result = mock_client.upload_file(
            filename='test.pdf',
            mime_type='application/pdf',
            file_path='/path/test.pdf',
            folder_id='folder123'
        )
        
        # Verify file_exists was called
        mock_client.file_exists.assert_called_once_with('test.pdf', 'folder123')
        assert result == 'new_file_456', "Should return new file ID"
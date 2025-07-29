import io
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError


class GoogleDriveClient:
    """Simplified client for Google Drive API operations."""
    
    # Google Drive API scopes
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self):
        """Initialize the Google Drive client."""
        self.logger = logging.getLogger(__name__)
        self.service = None
        self.credentials = None
        
    def authenticate(self) -> bool:
        """Authenticate with Google Drive API.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            creds = None
            token_path = Path('token.json')
            credentials_path = Path('credentials.json')
            
            # Load existing token
            if token_path.exists():
                creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
            
            # If no valid credentials, get new ones
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if not credentials_path.exists():
                        self.logger.error("credentials.json not found. Please download it from Google Cloud Console.")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, self.SCOPES)
                    creds = flow.run_local_server(port=8080)
                
                # Save credentials for next run
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            
            self.credentials = creds
            self.service = build('drive', 'v3', credentials=creds)
            self.logger.info("Google Drive authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Google Drive authentication failed: {e}")
            return False
    
    def get_all_folders(self) -> List[Dict[str, str]]:
        """Get all folders in Google Drive.
        
        Returns:
            list: List of folder dictionaries with 'id' and 'name' keys
        """
        try:
            folders = []
            page_token = None
            
            while True:
                query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = self.service.files().list(
                    q=query,
                    fields="nextPageToken, files(id, name, parents)",
                    pageToken=page_token
                ).execute()
                
                items = results.get('files', [])
                for item in items:
                    folders.append({
                        'id': item['id'],
                        'name': item['name'],
                        'parents': item.get('parents', [])
                    })
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            self.logger.info(f"Retrieved {len(folders)} folders from Google Drive")
            return folders
            
        except HttpError as e:
            self.logger.error(f"Failed to get folders: {e}")
            return []
    
    def upload_file(self, file_content: bytes, filename: str, mime_type: str, 
                   folder_id: Optional[str] = None) -> Optional[str]:
        """Upload a file to Google Drive.
        
        Args:
            file_content: File content as bytes
            filename: Name of the file
            mime_type: MIME type of the file
            folder_id: ID of folder to upload to (None for root)
            
        Returns:
            str: File ID if successful, None otherwise
        """
        try:
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            self.logger.info(f"Uploaded file '{filename}' with ID: {file_id}")
            return file_id
            
        except HttpError as e:
            self.logger.error(f"Failed to upload file '{filename}': {e}")
            return None
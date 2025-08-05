import io
import logging
from typing import Optional, List, Dict, Any, Callable
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
    
    def file_exists(self, filename: str, folder_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Check if a file with the given name already exists in the specified folder.
        
        Args:
            filename: Name of the file to check
            folder_id: ID of the folder to search in (None for root)
            
        Returns:
            Dict containing file info if file exists, None otherwise
        """
        try:
            # Build search query
            query = f"name = '{filename}' and trashed = false"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, size, createdTime)'
            ).execute()
            
            files = results.get('files', [])
            if files:
                existing_file = files[0]  # Return first match
                self.logger.info(f"File '{filename}' already exists with ID: {existing_file['id']}")
                return existing_file
            
            return None
            
        except HttpError as e:
            error_code = getattr(e, 'resp', {}).get('status', 'Unknown')
            self.logger.error(f"Failed to check file existence for '{filename}' (HTTP {error_code}): {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error checking file existence for '{filename}': {e}")
            return None
    
    def get_folder_id(self, folder_name: str = "UniMelb-2025-S2", parent_id: Optional[str] = None) -> Optional[str]:
        """Get the ID of a folder by name, creating it if it doesn't exist.
        
        Args:
            folder_name: Name of the folder to find or create (default: UniMelb-2025-S2)
            parent_id: ID of the parent folder (None for root)
            
        Returns:
            str: Folder ID if found or created, None otherwise
        """
        try:
            # Search for the folder
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            files = results.get('files', [])
            if files:
                folder_id = files[0].get('id')
                self.logger.info(f"Found folder '{folder_name}' with ID: {folder_id}")
                return folder_id
            
            self.logger.info(f"Folder '{folder_name}' not found, creating it")
            
            # Create the folder if it doesn't exist
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_id:
                file_metadata['parents'] = [parent_id]
                
            folder = self.service.files().create(
                body=file_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            self.logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
            
        except HttpError as e:
            error_code = getattr(e, 'resp', {}).get('status', 'Unknown')
            self.logger.error(f"Failed to find or create folder '{folder_name}' (HTTP {error_code}): {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error for folder '{folder_name}': {e}")
            return None
    
    def upload_file(self, 
                    filename: str,
                    mime_type: str,
                    file_content: Optional[bytes] = None,
                    file_path: Optional[str] = None,
                    folder_id: Optional[str] = None,
                    description: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None,
                    progress_callback: Optional[Callable[[float], None]] = None) -> Optional[str]:
        """Upload a file to Google Drive from bytes or a local file path.
        
        Args:
            filename: Name of the file to be stored in Google Drive
            mime_type: MIME type of the file
            file_content: File content as bytes (optional, use if no file_path)
            file_path: Local path to the file (optional, use if no file_content)
            folder_id: ID of folder to upload to (None for root)
            description: Optional description for the file
            metadata: Optional additional metadata for the file
            progress_callback: Optional callback function to report upload progress (0.0 to 1.0)
            
        Returns:
            str: File ID if successful, None otherwise
        
        Raises:
            ValueError: If neither file_content nor file_path is provided
        """
        try:
            if file_content is None and file_path is None:
                raise ValueError("Either file_content or file_path must be provided")
            
            # Check if file already exists
            existing_file = self.file_exists(filename, folder_id)
            if existing_file:
                self.logger.info(f"File '{filename}' already exists in folder, skipping upload")
                return existing_file['id']
            
            # Prepare file metadata
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            if description:
                file_metadata['description'] = description
            if metadata:
                file_metadata.update(metadata)
            
            # Prepare media upload
            if file_path:
                # Verify file exists
                if not Path(file_path).is_file():
                    self.logger.error(f"File not found: {file_path}")
                    return None
                media = MediaIoBaseUpload(
                    open(file_path, 'rb'),
                    mimetype=mime_type,
                    resumable=True
                )
            else:
                media = MediaIoBaseUpload(
                    io.BytesIO(file_content),
                    mimetype=mime_type,
                    resumable=True
                )
            
            # Create the upload request
            request = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            )
            
            # Execute the upload with progress tracking if callback provided
            if progress_callback:
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        progress_callback(status.progress())
            
            file = request.execute()
            file_id = file.get('id')
            self.logger.info(f"Uploaded file '{filename}' with ID: {file_id}")
            return file_id
            
        except HttpError as e:
            error_code = getattr(e, 'resp', {}).get('status', 'Unknown')
            self.logger.error(f"Failed to upload file '{filename}' (HTTP {error_code}): {e}")
            return None
        except ValueError as e:
            self.logger.error(f"Invalid input for file '{filename}': {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error uploading file '{filename}': {e}")
            return None
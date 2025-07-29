# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CanvasToDrive is a Python project that downloads files from Canvas LMS courses and uploads them to Google Drive. The project includes a Canvas API client for fetching course content and a Google Drive client for file uploads.

## Technology Stack

- **Language**: Python 3.8+
- **Canvas Integration**: aiohttp for async API calls to Canvas LMS REST API
- **Google Drive Integration**: google-api-python-client with OAuth2 authentication
- **Configuration**: python-dotenv for environment variables
- **Testing**: pytest with async support and coverage reporting

## Development Setup

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate
# Activate virtual environment (macOS/Linux)  
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Project Structure

```
src/
├── canvas_client.py    # Canvas LMS API client with async support
├── drive_client.py     # Google Drive API client (simplified)
└── config.py          # Configuration management with validation

tests/
├── test_canvas_client.py  # Comprehensive unit tests (58 test methods)
└── __init__.py

demo_canvas_to_drive.py    # Complete demo script
requirements.txt           # All dependencies
pytest.ini                # Test configuration
```

## Common Development Tasks

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_canvas_client.py -v
```

### Demo Script Usage
```bash
# Run the interactive demo
python demo_canvas_to_drive.py
```

## Configuration Requirements

### Canvas API Setup
Create `.env` file in project root:
```env
CANVAS_API_TOKEN=your_canvas_token_here
```

### Google Drive API Setup
1. Download OAuth2 credentials from Google Cloud Console
2. Save as `credentials.json` in project root
3. `token.json` will be auto-generated on first authentication

## Core Components

### CanvasClient
- **Async operations** using aiohttp for better performance
- **Paginated API calls** for large datasets
- **File download and Google Drive upload** integration
- **Error handling** with proper logging
- **Content processing** for different item types (pages, files, quizzes)

Key methods:
- `get_active_courses()` - List user's active courses
- `get_course_modules()` - Get all modules in a course
- `get_file_content()` - Download files and upload to Google Drive
- `get_assignments()` / `get_quizzes()` - Get course content

### GoogleDriveClient (Simplified)
- **OAuth2 authentication** with token persistence
- **File upload** to any existing folder
- **Folder discovery** via `get_all_folders()`
- **No automatic folder creation** - uses existing Drive structure

Key methods:
- `authenticate()` - Handle OAuth2 flow
- `get_all_folders()` - List all available Drive folders
- `upload_file()` - Upload file to specified folder

### Configuration Management
- **Environment variable validation** on import
- **Required settings**: Canvas API token
- **Error handling** for missing configuration

## API Integration Details

### Canvas LMS REST API
- **Base URL**: Configured via Config.CANVAS_URL
- **Authentication**: Bearer token via Canvas API token
- **Rate limiting**: Handled through async operations
- **Pagination**: Automatic handling of paginated responses

### Google Drive API v3
- **Scopes**: `drive.file` (create and edit files only)
- **Authentication**: OAuth2 with local server flow
- **File types**: Supports all file types (PDF, PPTX, images, etc.)
- **Folder organization**: Uses existing Drive folder structure

## Testing

Comprehensive test suite with 58+ test methods covering:
- **Unit tests** for all Canvas client methods
- **Mock-based testing** for HTTP operations
- **Error scenario testing** for robustness
- **Integration tests** for multi-method workflows
- **80%+ test coverage** target

## Security Considerations

- **Credentials excluded** from git (.gitignore configured)
- **Token-based authentication** for both APIs
- **No hardcoded secrets** in source code
- **Environment-based configuration** for sensitive data
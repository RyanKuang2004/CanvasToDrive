# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CanvasToDrive is a Python project designed to automatically upload documents from Canvas LMS into Google Drive. The project is currently in its initial setup phase with no source code implemented yet.

## Technology Stack

Based on the .gitignore configuration, this project is intended to be:
- **Language**: Python
- **Purpose**: Integration between Canvas LMS and Google Drive APIs
- **Architecture**: Not yet established (awaiting initial implementation)

## Development Setup

Since the project is in early stages, the development environment setup will need to be established. Typical Python project setup would involve:

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate
# Activate virtual environment (macOS/Linux)  
source venv/bin/activate

# Install dependencies (once requirements.txt is created)
pip install -r requirements.txt
```

## Project Structure (To Be Implemented)

The project structure is not yet established. Common patterns for this type of integration project would include:
- Authentication modules for both Canvas and Google Drive APIs
- Data retrieval and processing components
- Upload and synchronization logic
- Configuration management
- Error handling and logging

## API Integration Requirements

This project will likely need to integrate with:
- **Canvas LMS REST API**: For retrieving course documents and files
- **Google Drive API**: For uploading and organizing files
- Authentication handling for both services (OAuth2 flows)

## Next Steps for Initial Development

1. Set up project dependencies (requests, google-api-python-client, etc.)
2. Create project structure with appropriate modules
3. Implement authentication for both Canvas and Google Drive
4. Develop core functionality for document retrieval and upload
5. Add configuration management for API credentials
6. Implement error handling and logging
7. Create tests for core functionality

## Important Considerations

- API credentials and tokens should never be committed to the repository
- Rate limiting and API quotas need to be considered for both services  
- File organization strategy in Google Drive should be planned
- Error recovery and retry logic will be important for reliability
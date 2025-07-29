import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
load_dotenv(project_root / '.env')


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""
    pass


class Config:
    """Configuration management for Canvas API client.
    
    Loads configuration from environment variables with validation.
    """
    
    # Canvas API Configuration
    CANVAS_URL: str = 'https://canvas.lms.unimelb.edu.au/api/v1'
    CANVAS_API_TOKEN: Optional[str] = os.getenv('CANVAS_API_TOKEN')
    
    @classmethod
    def validate(cls) -> None:
        """Validate that required configuration is present.
        
        Raises:
            ConfigurationError: If required configuration is missing or invalid
        """
        if not cls.CANVAS_API_TOKEN:
            raise ConfigurationError(
                "CANVAS_API_TOKEN environment variable is required. "
                "Please set it in your .env file or environment."
            )
        
        if not cls.CANVAS_URL:
            raise ConfigurationError("CANVAS_URL cannot be empty")
        
        # Basic URL format validation
        if not cls.CANVAS_URL.startswith(('http://', 'https://')):
            raise ConfigurationError("CANVAS_URL must be a valid HTTP/HTTPS URL")
    
    @classmethod
    def get_canvas_base_url(cls) -> str:
        """Get the base Canvas URL without the API version.
        
        Returns:
            The base Canvas URL
        """
        return cls.CANVAS_URL.replace('/api/v1', '')


# Validate configuration on import
Config.validate()
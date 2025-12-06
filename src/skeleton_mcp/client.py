"""
API Client Module

This module handles communication with your backend API.
Customize this to connect to your specific API endpoints.
"""

import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load environment variables from multiple possible locations
_env_paths = [
    Path.cwd() / ".env",
    Path(__file__).parent.parent.parent.parent / ".env",
    Path.home() / ".env",
]

for env_path in _env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        break


def get_client_config() -> dict[str, Any]:
    """
    Get the client configuration from environment variables.

    Returns:
        A dictionary with configuration values.
    """
    return {
        "api_key": os.getenv("API_KEY"),
        "api_base_url": os.getenv("API_BASE_URL", "https://api.example.com/v1"),
        "timeout": int(os.getenv("API_TIMEOUT", "30")),
        "debug": os.getenv("DEBUG", "false").lower() == "true",
    }


class APIClient:
    """
    A simple HTTP client for making API requests.

    Customize this class to match your API's authentication
    and request patterns.
    """

    def __init__(self) -> None:
        config = get_client_config()
        self.base_url = config["api_base_url"]
        self.timeout = config["timeout"]
        self.api_key = config["api_key"]

        self.session = requests.Session()
        if self.api_key:
            # Customize the authentication header as needed
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"
        self.session.headers["Content-Type"] = "application/json"

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request to the API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a POST request to the API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def put(self, endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a PUT request to the API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.put(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def delete(self, endpoint: str) -> dict[str, Any]:
        """Make a DELETE request to the API."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.delete(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()


# Singleton client instance
_client: APIClient | None = None


def get_client() -> APIClient:
    """Get the API client singleton instance."""
    global _client
    if _client is None:
        _client = APIClient()
    return _client

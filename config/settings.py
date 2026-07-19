"""Application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for Foundry and ServiceNow integrations."""

    foundry_project_endpoint: str
    foundry_model_deployment: str
    foundry_api_version: str
    servicenow_instance_url: str
    servicenow_username: str
    servicenow_password: str
    servicenow_timeout_seconds: int = 15
    servicenow_max_retries: int = 3



def load_settings() -> Settings:
    """Load settings from environment variables and .env file."""

    load_dotenv()
    return Settings(
        foundry_project_endpoint=os.getenv("AZURE_AI_FOUNDRY_PROJECT_ENDPOINT", ""),
        foundry_model_deployment=os.getenv("AZURE_AI_FOUNDRY_MODEL_DEPLOYMENT", ""),
        foundry_api_version=os.getenv("AZURE_AI_FOUNDRY_API_VERSION", ""),
        servicenow_instance_url=os.getenv("SERVICENOW_INSTANCE_URL", ""),
        servicenow_username=os.getenv("SERVICENOW_USERNAME", ""),
        servicenow_password=os.getenv("SERVICENOW_PASSWORD", ""),
        servicenow_timeout_seconds=int(os.getenv("SERVICENOW_TIMEOUT_SECONDS", "15")),
        servicenow_max_retries=int(os.getenv("SERVICENOW_MAX_RETRIES", "3")),
    )

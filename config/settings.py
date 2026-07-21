"""
config/settings.py
------------------
Central configuration loaded from environment variables / .env file.
All other modules import from here — never import os.environ directly.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Azure AI Foundry
    ai_project_endpoint: str = os.environ.get("AZURE_AI_PROJECT_ENDPOINT", "")
    foundry_model_name: str = os.environ.get("AZURE_FOUNDRY_MODEL_NAME", "gpt-4o")

    # Azure subscription
    subscription_id: str = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
    resource_group: str = os.environ.get("AZURE_RESOURCE_GROUP", "")

    # Log Analytics
    log_analytics_workspace_id: str = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "")

    # Azure Automation
    automation_account_name: str = os.environ.get("AUTOMATION_ACCOUNT_NAME", "")
    automation_resource_group: str = os.environ.get(
        "AUTOMATION_RESOURCE_GROUP", os.environ.get("AZURE_RESOURCE_GROUP", "")
    )

    # Approval mode: "auto" | "manual"
    approval_mode: str = os.environ.get("APPROVAL_MODE", "manual")
    teams_webhook_url: str = os.environ.get("TEAMS_WEBHOOK_URL", "")


settings = Settings()

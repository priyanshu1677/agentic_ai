"""
Google Workspace Authentication - Shared OAuth handler for all Google services.
"""

import os
import time
import requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# All scopes for Google Workspace
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/forms.body",
]

# Gumloop API config
GUMLOOP_API_KEY = "8556c06b71de440d965718fd8e19d352"
GUMLOOP_USER_ID = "hx5C9Y6io9enVlAg3TKHaB2gdvJ3"
GUMLOOP_PIPELINE_ID = "6oKS6Ca67hQdgqnXDVhYDL"

# Token file path
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")


def get_credentials():
    """Get or refresh OAuth credentials for all Google services."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


def get_service(service_name, version):
    """Build a Google API service."""
    creds = get_credentials()
    return build(service_name, version, credentials=creds)


# Service factory functions
def get_calendar_service():
    return get_service("calendar", "v3")


def get_gmail_service():
    return get_service("gmail", "v1")


def get_drive_service():
    return get_service("drive", "v3")


def get_docs_service():
    return get_service("docs", "v1")


def get_sheets_service():
    return get_service("sheets", "v4")


def get_slides_service():
    return get_service("slides", "v1")


def get_tasks_service():
    return get_service("tasks", "v1")


def get_people_service():
    """Get People API service for contacts."""
    return get_service("people", "v1")


def get_forms_service():
    return get_service("forms", "v1")


def call_gumloop(prompt: str) -> str:
    """Call Gumloop AI for natural language processing."""
    url = "https://api.gumloop.com/api/v1/start_pipeline"
    params = {
        "api_key": GUMLOOP_API_KEY,
        "user_id": GUMLOOP_USER_ID,
        "saved_item_id": GUMLOOP_PIPELINE_ID
    }
    payload = {"pipeline_inputs": [{"input_name": "input", "value": prompt}]}

    response = requests.post(url, params=params, json=payload)
    result = response.json()

    if "run_id" in result:
        run_id = result["run_id"]
        for _ in range(30):
            time.sleep(2)
            status = requests.get(
                "https://api.gumloop.com/api/v1/get_pl_run",
                params={"api_key": GUMLOOP_API_KEY, "user_id": GUMLOOP_USER_ID, "run_id": run_id}
            ).json()
            if status.get("state") == "DONE":
                return status.get("outputs", {}).get("output", "No response")
            elif status.get("state") in ["FAILED", "ERROR"]:
                return "AI request failed"
    return "AI request failed"


if __name__ == "__main__":
    # Test authentication
    print("Testing Google Workspace Authentication...")
    try:
        creds = get_credentials()
        print("Authentication successful!")
        print(f"Token saved to: {TOKEN_FILE}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Authentication failed: {e}")

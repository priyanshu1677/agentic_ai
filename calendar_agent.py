import os
import datetime
import requests
import time
import json
import re
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Gumloop API config
GUMLOOP_API_KEY = "8556c06b71de440d965718fd8e19d352"
GUMLOOP_USER_ID = "hx5C9Y6io9enVlAg3TKHaB2gdvJ3"
GUMLOOP_PIPELINE_ID = "6oKS6Ca67hQdgqnXDVhYDL"

def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("credentials.json"):
                raise FileNotFoundError("credentials.json not found")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def call_gumloop(prompt: str) -> str:
    """Call Gumloop for AI responses."""
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

def list_events(service, max_results=10):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events_result = service.events().list(
        calendarId="primary", timeMin=now, maxResults=max_results,
        singleEvents=True, orderBy="startTime"
    ).execute()
    events = events_result.get("items", [])

    if not events:
        return "No upcoming events found."

    result = "\nYour upcoming events:\n"
    for i, event in enumerate(events, 1):
        start = event["start"].get("dateTime", event["start"].get("date"))
        summary = event.get("summary", "No title")
        result += f"  {i}. {start[:10]} - {summary}\n"
    return result

def create_event(service, summary, start_date, end_date=None, all_day=True):
    if all_day:
        if not end_date:
            end_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d") + datetime.timedelta(days=1)
            end_date = end_dt.strftime("%Y-%m-%d")
        event = {
            "summary": summary,
            "start": {"date": start_date},
            "end": {"date": end_date},
        }
    else:
        event = {
            "summary": summary,
            "start": {"dateTime": start_date, "timeZone": "UTC"},
            "end": {"dateTime": end_date, "timeZone": "UTC"},
        }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return f"Done! Created '{summary}' for {start_date}"

def delete_event_by_name(service, event_name):
    """Delete event by searching for its name."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events = service.events().list(
        calendarId="primary", timeMin=now, maxResults=100, singleEvents=True
    ).execute().get("items", [])

    event_name_lower = event_name.lower()
    for event in events:
        if event_name_lower in event.get("summary", "").lower():
            service.events().delete(calendarId="primary", eventId=event["id"]).execute()
            return f"Deleted '{event.get('summary')}'"

    return f"Could not find event matching '{event_name}'"

def parse_date(text, days_offset=0):
    """Convert natural language to date."""
    today = datetime.date.today()

    if "today" in text.lower():
        return (today + datetime.timedelta(days=days_offset)).strftime("%Y-%m-%d")
    elif "tomorrow" in text.lower():
        return (today + datetime.timedelta(days=1 + days_offset)).strftime("%Y-%m-%d")
    elif "next" in text.lower() and "day" in text.lower():
        # Extract number of days
        match = re.search(r'(\d+)\s*day', text.lower())
        if match:
            days = int(match.group(1))
            return (today + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    # Check for "in X days"
    match = re.search(r'in\s*(\d+)\s*day', text.lower())
    if match:
        days = int(match.group(1))
        return (today + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    # Check for explicit date
    match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if match:
        return match.group(1)

    return None

def process_with_ai(service, user_input):
    """Use AI to understand and execute calendar commands."""

    # Get current events for context
    events_context = list_events(service)
    today = datetime.date.today().strftime("%Y-%m-%d")

    prompt = f"""You are a calendar assistant. Today is {today}.

User's calendar:
{events_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For creating events:
{{"action": "create", "title": "event name", "date": "YYYY-MM-DD"}}

For listing events:
{{"action": "list"}}

For deleting events:
{{"action": "delete", "title": "event name to search for"}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        # Try to extract JSON from response
        json_match = re.search(r'\{[^}]+\}', ai_response)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "create":
                title = data.get("title", "Event")
                date = data.get("date")
                if date:
                    return create_event(service, title, date)
                else:
                    return "I couldn't understand the date. Please specify like: 'schedule Meeting on 2026-02-05'"

            elif data.get("action") == "list":
                return list_events(service)

            elif data.get("action") == "delete":
                title = data.get("title", "")
                if title:
                    return delete_event_by_name(service, title)
                return "Which event do you want to delete?"

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except:
        return ai_response

def main():
    print("=" * 50)
    print("Calendar Agent")
    print("=" * 50)

    try:
        service = get_calendar_service()
        print("Connected to Google Calendar!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my events'")
    print("  - 'Schedule a meeting called Rahul in 2 days'")
    print("  - 'Delete the Mela Event'")
    print("  - 'What's on my calendar?'")
    print("\nType 'quit' to exit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except EOFError:
            break

        if not user_input:
            continue

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        # Quick commands (no AI needed)
        if user_input.lower() in ["list", "events", "show events", "show my events"]:
            print(list_events(service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(service, user_input)
        print(f"\nAssistant: {response}\n")

if __name__ == "__main__":
    main()

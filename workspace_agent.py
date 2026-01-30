"""
Unified Google Workspace Agent - Single interface for all Google services.
Routes natural language requests to the appropriate service agent.
"""

import json
import re
from datetime import datetime
from google_auth import (
    get_calendar_service, get_gmail_service, get_drive_service,
    get_docs_service, get_sheets_service, get_slides_service,
    get_tasks_service, get_people_service, get_forms_service,
    call_gumloop
)

# Import agent functions
from calendar_agent import list_events, create_event, delete_event_by_name
from gmail_agent import list_messages, search_messages, send_email, get_unread_count
from drive_agent import list_files, search_files, create_folder, upload_file, share_file
from docs_agent import list_docs, create_document, get_document, append_text
from sheets_agent import list_spreadsheets, create_spreadsheet, read_range, append_row
from slides_agent import list_presentations, create_presentation, add_slide
from tasks_agent import list_tasks, create_task, complete_task, list_task_lists
from contacts_agent import list_contacts, search_contacts, create_contact
from forms_agent import list_forms, create_form, add_question, get_responses


def get_all_services():
    """Initialize all Google services."""
    return {
        "calendar": get_calendar_service(),
        "gmail": get_gmail_service(),
        "drive": get_drive_service(),
        "docs": get_docs_service(),
        "sheets": get_sheets_service(),
        "slides": get_slides_service(),
        "tasks": get_tasks_service(),
        "contacts": get_people_service(),
        "forms": get_forms_service()
    }


def get_context_summary(services):
    """Get a brief summary of each service for context."""
    summary = []

    # Calendar
    try:
        events = list_events(services["calendar"], 3)
        summary.append(f"Calendar: {events[:100]}...")
    except:
        summary.append("Calendar: Connected")

    # Gmail
    try:
        unread = get_unread_count(services["gmail"])
        summary.append(f"Gmail: {unread} unread emails")
    except:
        summary.append("Gmail: Connected")

    # Tasks
    try:
        tasks = list_tasks(services["tasks"])
        task_count = tasks.count("[ ]")
        summary.append(f"Tasks: {task_count} pending tasks")
    except:
        summary.append("Tasks: Connected")

    return "\n".join(summary)


def route_request(services, user_input):
    """Use AI to route the request to the appropriate service and execute it."""

    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    context = get_context_summary(services)

    prompt = f"""You are a Google Workspace assistant managing: Calendar, Gmail, Drive, Docs, Sheets, Slides, Tasks, Contacts, and Forms.

Today is {today}.

Quick Status:
{context}

User request: "{user_input}"

Analyze the request and determine which service to use. Respond with ONE JSON:

For CALENDAR operations:
{{"service": "calendar", "action": "list"}}
{{"service": "calendar", "action": "create", "title": "Event name", "date": "YYYY-MM-DD"}}
{{"service": "calendar", "action": "delete", "title": "event name"}}

For GMAIL operations:
{{"service": "gmail", "action": "list"}}
{{"service": "gmail", "action": "unread"}}
{{"service": "gmail", "action": "search", "query": "search term"}}
{{"service": "gmail", "action": "send", "to": "email@example.com", "subject": "Subject", "body": "Body"}}

For DRIVE operations:
{{"service": "drive", "action": "list"}}
{{"service": "drive", "action": "search", "query": "file name"}}
{{"service": "drive", "action": "create_folder", "name": "Folder Name"}}
{{"service": "drive", "action": "share", "name": "file name", "email": "user@email.com"}}

For DOCS operations:
{{"service": "docs", "action": "list"}}
{{"service": "docs", "action": "create", "title": "Document Title"}}
{{"service": "docs", "action": "read", "name": "document name"}}

For SHEETS operations:
{{"service": "sheets", "action": "list"}}
{{"service": "sheets", "action": "create", "title": "Spreadsheet Title"}}
{{"service": "sheets", "action": "read", "name": "spreadsheet name", "range": "Sheet1!A1:Z100"}}
{{"service": "sheets", "action": "append", "name": "spreadsheet name", "values": ["col1", "col2"]}}

For SLIDES operations:
{{"service": "slides", "action": "list"}}
{{"service": "slides", "action": "create", "title": "Presentation Title"}}

For TASKS operations:
{{"service": "tasks", "action": "list"}}
{{"service": "tasks", "action": "create", "title": "Task name", "due": "YYYY-MM-DD or null"}}
{{"service": "tasks", "action": "complete", "title": "task name"}}

For CONTACTS operations:
{{"service": "contacts", "action": "list"}}
{{"service": "contacts", "action": "search", "query": "name"}}
{{"service": "contacts", "action": "create", "name": "Name", "email": "email", "phone": "phone"}}

For FORMS operations:
{{"service": "forms", "action": "list"}}
{{"service": "forms", "action": "create", "title": "Form Title"}}
{{"service": "forms", "action": "responses", "name": "form name"}}

For status/overview:
{{"service": "status", "action": "overview"}}

For general chat:
{{"service": "chat", "response": "your helpful response"}}

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            service_name = data.get("service")
            action = data.get("action")

            # CALENDAR
            if service_name == "calendar":
                if action == "list":
                    return list_events(services["calendar"])
                elif action == "create":
                    return create_event(services["calendar"], data.get("title"), data.get("date"))
                elif action == "delete":
                    return delete_event_by_name(services["calendar"], data.get("title"))

            # GMAIL
            elif service_name == "gmail":
                if action == "list":
                    return list_messages(services["gmail"])
                elif action == "unread":
                    return list_messages(services["gmail"], 10, "is:unread")
                elif action == "search":
                    return search_messages(services["gmail"], data.get("query"))
                elif action == "send":
                    return send_email(services["gmail"], data.get("to"), data.get("subject"), data.get("body", ""))

            # DRIVE
            elif service_name == "drive":
                if action == "list":
                    return list_files(services["drive"])
                elif action == "search":
                    return search_files(services["drive"], data.get("query"))
                elif action == "create_folder":
                    return create_folder(services["drive"], data.get("name"))

            # DOCS
            elif service_name == "docs":
                if action == "list":
                    return list_docs(services["drive"])
                elif action == "create":
                    result = create_document(services["docs"], data.get("title"))
                    return f"Created '{result['title']}'\nURL: {result['url']}"

            # SHEETS
            elif service_name == "sheets":
                if action == "list":
                    return list_spreadsheets(services["drive"])
                elif action == "create":
                    result = create_spreadsheet(services["sheets"], data.get("title"))
                    return f"Created '{result['title']}'\nURL: {result['url']}"

            # SLIDES
            elif service_name == "slides":
                if action == "list":
                    return list_presentations(services["drive"])
                elif action == "create":
                    result = create_presentation(services["slides"], data.get("title"))
                    return f"Created '{result['title']}'\nURL: {result['url']}"

            # TASKS
            elif service_name == "tasks":
                if action == "list":
                    return list_tasks(services["tasks"])
                elif action == "create":
                    return create_task(services["tasks"], data.get("title"), "", data.get("due"))
                elif action == "complete":
                    from tasks_agent import get_task_by_title
                    task = get_task_by_title(services["tasks"], data.get("title"))
                    if task:
                        return complete_task(services["tasks"], task["id"])
                    return "Could not find that task."

            # CONTACTS
            elif service_name == "contacts":
                if action == "list":
                    return list_contacts(services["contacts"])
                elif action == "search":
                    return search_contacts(services["contacts"], data.get("query"))
                elif action == "create":
                    return create_contact(services["contacts"], data.get("name"), data.get("email"), data.get("phone"))

            # FORMS
            elif service_name == "forms":
                if action == "list":
                    return list_forms(services["drive"])
                elif action == "create":
                    result = create_form(services["forms"], data.get("title"))
                    return f"Created '{result['title']}'\nURL: {result['url']}"

            # STATUS
            elif service_name == "status":
                output = "\n=== WORKSPACE STATUS ===\n"
                output += f"Date: {today}\n\n"

                # Calendar
                output += "CALENDAR:\n"
                output += list_events(services["calendar"], 5) + "\n"

                # Tasks
                output += "TASKS:\n"
                output += list_tasks(services["tasks"]) + "\n"

                # Gmail
                output += "GMAIL:\n"
                unread = get_unread_count(services["gmail"])
                output += f"  {unread} unread emails\n"

                return output

            # CHAT
            elif service_name == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 60)
    print("Google Workspace Agent - Unified Interface")
    print("=" * 60)

    print("\nConnecting to Google services...")

    try:
        services = get_all_services()
        print("Connected to all Google Workspace services!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! I can help with:")
    print("  Calendar: 'What's on my calendar?', 'Schedule meeting tomorrow'")
    print("  Gmail:    'Show unread emails', 'Send email to john@example.com'")
    print("  Drive:    'Show my files', 'Create folder Projects'")
    print("  Docs:     'Create document Meeting Notes', 'List my documents'")
    print("  Sheets:   'Create spreadsheet Budget', 'Show my spreadsheets'")
    print("  Slides:   'Create presentation Q1 Report'")
    print("  Tasks:    'Add task: Buy groceries', 'Show my tasks'")
    print("  Contacts: 'Find John's number', 'Add contact Jane'")
    print("  Forms:    'Create feedback form', 'Show form responses'")
    print("  Status:   'Give me an overview', 'What's my status?'")
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

        # Quick commands
        if user_input.lower() in ["status", "overview", "summary"]:
            output = "\n=== QUICK STATUS ===\n"
            output += f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            output += "Calendar:\n" + list_events(services["calendar"], 3) + "\n"
            output += "Tasks:\n" + list_tasks(services["tasks"]) + "\n"
            output += f"Gmail: {get_unread_count(services['gmail'])} unread\n"
            print(output)
            continue

        if user_input.lower() in ["help", "?"]:
            print("\nAvailable services:")
            print("  calendar - Manage events")
            print("  gmail    - Read/send emails")
            print("  drive    - Manage files")
            print("  docs     - Create/edit documents")
            print("  sheets   - Work with spreadsheets")
            print("  slides   - Create presentations")
            print("  tasks    - Manage to-do list")
            print("  contacts - Manage contacts")
            print("  forms    - Create/view forms")
            print("\nJust ask naturally - I'll figure out what you need!\n")
            continue

        # Use AI for routing
        print("Thinking...")
        response = route_request(services, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

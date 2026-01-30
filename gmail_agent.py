"""
Gmail Agent - Natural language interface for Gmail operations.
"""

import os
import json
import re
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from google_auth import get_gmail_service, call_gumloop


def list_messages(service, max_results=10, query=""):
    """List messages from inbox."""
    results = service.users().messages().list(
        userId="me", maxResults=max_results, q=query
    ).execute()
    messages = results.get("messages", [])

    if not messages:
        return "No messages found."

    output = f"\nFound {len(messages)} message(s):\n"
    for i, msg in enumerate(messages[:max_results], 1):
        message = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "No subject")[:50]
        sender = headers.get("From", "Unknown")[:40]
        date = headers.get("Date", "")[:16]

        output += f"  {i}. {subject}\n     From: {sender} | {date}\n"

    return output


def get_unread_count(service):
    """Get count of unread messages."""
    results = service.users().messages().list(
        userId="me", q="is:unread", maxResults=100
    ).execute()
    messages = results.get("messages", [])
    return len(messages)


def read_message(service, message_id):
    """Read a specific message by ID."""
    message = service.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}

    # Extract body
    body = ""
    payload = message.get("payload", {})
    if "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
    elif "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain" and part["body"].get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break

    return {
        "subject": headers.get("Subject", "No subject"),
        "from": headers.get("From", "Unknown"),
        "date": headers.get("Date", "Unknown"),
        "body": body[:1000] if body else "No body content"
    }


def search_messages(service, query, max_results=10):
    """Search for messages matching query."""
    results = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = results.get("messages", [])

    if not messages:
        return f"No messages found matching '{query}'."

    output = f"\nFound {len(messages)} message(s) for '{query}':\n"
    for i, msg in enumerate(messages, 1):
        message = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = {h["name"]: h["value"] for h in message.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "No subject")[:50]
        sender = headers.get("From", "Unknown")[:40]

        output += f"  {i}. {subject}\n     From: {sender}\n"

    return output


def send_email(service, to, subject, body):
    """Send an email."""
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    sent = service.users().messages().send(
        userId="me", body={"raw": raw}
    ).execute()

    return f"Email sent to {to} with subject '{subject}'"


def trash_message(service, message_id):
    """Move a message to trash."""
    service.users().messages().trash(userId="me", id=message_id).execute()
    return "Message moved to trash."


def list_labels(service):
    """List all labels."""
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])

    output = "\nYour labels:\n"
    for label in labels:
        output += f"  - {label['name']}\n"
    return output


def get_message_by_index(service, index, query=""):
    """Get message ID by index from a search."""
    results = service.users().messages().list(
        userId="me", maxResults=20, q=query
    ).execute()
    messages = results.get("messages", [])

    if index < 1 or index > len(messages):
        return None
    return messages[index - 1]["id"]


def process_with_ai(service, user_input):
    """Use AI to understand and execute Gmail commands."""

    # Get context
    unread_count = get_unread_count(service)
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""You are a Gmail assistant. Today is {today}.
User has {unread_count} unread emails.

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing emails:
{{"action": "list", "query": "optional search query", "count": 10}}

For searching emails:
{{"action": "search", "query": "search terms"}}

For reading an email (by number from list):
{{"action": "read", "index": 1}}

For sending email:
{{"action": "send", "to": "email@example.com", "subject": "Subject here", "body": "Email body here"}}

For deleting/trashing email (by number):
{{"action": "trash", "index": 1}}

For showing unread emails:
{{"action": "unread"}}

For listing labels:
{{"action": "labels"}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Common queries:
- "is:unread" for unread emails
- "from:sender@email.com" for emails from someone
- "subject:keyword" for subject search
- "has:attachment" for emails with attachments

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        json_match = re.search(r'\{[^}]+\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "list":
                query = data.get("query", "")
                count = data.get("count", 10)
                return list_messages(service, count, query)

            elif data.get("action") == "search":
                query = data.get("query", "")
                return search_messages(service, query)

            elif data.get("action") == "read":
                index = data.get("index", 1)
                msg_id = get_message_by_index(service, index)
                if msg_id:
                    msg = read_message(service, msg_id)
                    return f"\nSubject: {msg['subject']}\nFrom: {msg['from']}\nDate: {msg['date']}\n\n{msg['body']}"
                return "Could not find that email."

            elif data.get("action") == "send":
                to = data.get("to", "")
                subject = data.get("subject", "")
                body = data.get("body", "")
                if to and subject:
                    return send_email(service, to, subject, body)
                return "Need recipient and subject to send email."

            elif data.get("action") == "trash":
                index = data.get("index", 1)
                msg_id = get_message_by_index(service, index)
                if msg_id:
                    return trash_message(service, msg_id)
                return "Could not find that email."

            elif data.get("action") == "unread":
                return list_messages(service, 10, "is:unread")

            elif data.get("action") == "labels":
                return list_labels(service)

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Gmail Agent")
    print("=" * 50)

    try:
        service = get_gmail_service()
        print("Connected to Gmail!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my emails'")
    print("  - 'Show unread emails'")
    print("  - 'Search for emails from John'")
    print("  - 'Send email to jane@example.com about meeting'")
    print("  - 'Read email 1'")
    print("  - 'Delete email 2'")
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
        if user_input.lower() in ["list", "inbox", "emails", "show emails"]:
            print(list_messages(service))
            continue

        if user_input.lower() in ["unread", "show unread"]:
            print(list_messages(service, 10, "is:unread"))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

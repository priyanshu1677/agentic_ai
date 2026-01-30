"""
Google Drive Agent - Natural language interface for Drive operations.
"""

import os
import io
import json
import re
from datetime import datetime
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth import get_drive_service, call_gumloop


def list_files(service, max_results=10, query=None):
    """List files in Drive."""
    q = query if query else "trashed=false"
    results = service.files().list(
        pageSize=max_results,
        q=q,
        fields="files(id, name, mimeType, modifiedTime, size, parents)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if not files:
        return "No files found."

    output = f"\nYour files ({len(files)}):\n"
    for i, f in enumerate(files, 1):
        name = f["name"][:40]
        mime = f["mimeType"].split(".")[-1] if "." in f["mimeType"] else f["mimeType"][:20]
        modified = f.get("modifiedTime", "")[:10]
        output += f"  {i}. {name}\n     Type: {mime} | Modified: {modified}\n"

    return output


def search_files(service, query, max_results=10):
    """Search for files by name or content."""
    search_query = f"name contains '{query}' and trashed=false"
    results = service.files().list(
        pageSize=max_results,
        q=search_query,
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()
    files = results.get("files", [])

    if not files:
        return f"No files found matching '{query}'."

    output = f"\nFound {len(files)} file(s) matching '{query}':\n"
    for i, f in enumerate(files, 1):
        output += f"  {i}. {f['name']}\n"
    return output


def create_folder(service, name, parent_id=None):
    """Create a new folder."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder"
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id, name").execute()
    return f"Created folder '{name}'"


def upload_file(service, file_path, parent_id=None):
    """Upload a file to Drive."""
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    file_name = os.path.basename(file_path)
    metadata = {"name": file_name}
    if parent_id:
        metadata["parents"] = [parent_id]

    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(
        body=metadata, media_body=media, fields="id, name"
    ).execute()

    return f"Uploaded '{file_name}' to Drive"


def download_file(service, file_id, destination):
    """Download a file from Drive."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()

    with open(destination, "wb") as f:
        f.write(fh.getvalue())

    return f"Downloaded file to {destination}"


def delete_file(service, file_id):
    """Delete a file (move to trash)."""
    service.files().update(fileId=file_id, body={"trashed": True}).execute()
    return "File moved to trash."


def share_file(service, file_id, email, role="reader"):
    """Share a file with someone."""
    permission = {
        "type": "user",
        "role": role,
        "emailAddress": email
    }
    service.permissions().create(
        fileId=file_id, body=permission, sendNotificationEmail=True
    ).execute()
    return f"Shared file with {email} as {role}"


def get_file_by_name(service, name):
    """Get file ID by name."""
    query = f"name='{name}' and trashed=false"
    results = service.files().list(
        q=query, fields="files(id, name)", pageSize=1
    ).execute()
    files = results.get("files", [])
    return files[0] if files else None


def get_file_by_index(service, index):
    """Get file by index from recent files list."""
    results = service.files().list(
        pageSize=20,
        q="trashed=false",
        fields="files(id, name)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if index < 1 or index > len(files):
        return None
    return files[index - 1]


def process_with_ai(service, user_input):
    """Use AI to understand and execute Drive commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    files_context = list_files(service, 5)

    prompt = f"""You are a Google Drive assistant. Today is {today}.

Recent files:
{files_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing files:
{{"action": "list", "count": 10}}

For searching files:
{{"action": "search", "query": "search term"}}

For creating a folder:
{{"action": "create_folder", "name": "folder name"}}

For uploading a file (from local path):
{{"action": "upload", "path": "/path/to/file"}}

For downloading a file (by number from list):
{{"action": "download", "index": 1, "destination": "/path/to/save"}}

For deleting a file (by number or name):
{{"action": "delete", "index": 1}}

For sharing a file:
{{"action": "share", "index": 1, "email": "user@example.com", "role": "reader"}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Roles for sharing: "reader" (view only), "writer" (can edit), "commenter"

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        json_match = re.search(r'\{[^}]+\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "list":
                count = data.get("count", 10)
                return list_files(service, count)

            elif data.get("action") == "search":
                query = data.get("query", "")
                return search_files(service, query)

            elif data.get("action") == "create_folder":
                name = data.get("name", "New Folder")
                return create_folder(service, name)

            elif data.get("action") == "upload":
                path = data.get("path", "")
                return upload_file(service, path)

            elif data.get("action") == "download":
                index = data.get("index", 1)
                dest = data.get("destination", "./downloaded_file")
                file = get_file_by_index(service, index)
                if file:
                    return download_file(service, file["id"], dest)
                return "Could not find that file."

            elif data.get("action") == "delete":
                index = data.get("index", 1)
                file = get_file_by_index(service, index)
                if file:
                    delete_file(service, file["id"])
                    return f"Deleted '{file['name']}'"
                return "Could not find that file."

            elif data.get("action") == "share":
                index = data.get("index", 1)
                email = data.get("email", "")
                role = data.get("role", "reader")
                file = get_file_by_index(service, index)
                if file and email:
                    return share_file(service, file["id"], email, role)
                return "Need file and email to share."

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Drive Agent")
    print("=" * 50)

    try:
        service = get_drive_service()
        print("Connected to Google Drive!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my files'")
    print("  - 'Search for budget spreadsheet'")
    print("  - 'Create a folder called Projects'")
    print("  - 'Share file 1 with john@example.com'")
    print("  - 'Delete file 3'")
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
        if user_input.lower() in ["list", "files", "show files", "my files"]:
            print(list_files(service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

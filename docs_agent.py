"""
Google Docs Agent - Natural language interface for Docs operations.
"""

import json
import re
from datetime import datetime
from google_auth import get_docs_service, get_drive_service, call_gumloop


def create_document(docs_service, title):
    """Create a new Google Doc."""
    doc = docs_service.documents().create(body={"title": title}).execute()
    return {
        "id": doc.get("documentId"),
        "title": doc.get("title"),
        "url": f"https://docs.google.com/document/d/{doc.get('documentId')}/edit"
    }


def get_document(docs_service, document_id):
    """Get document content."""
    doc = docs_service.documents().get(documentId=document_id).execute()

    # Extract text content
    content = ""
    for element in doc.get("body", {}).get("content", []):
        if "paragraph" in element:
            for para_element in element["paragraph"].get("elements", []):
                if "textRun" in para_element:
                    content += para_element["textRun"].get("content", "")

    return {
        "id": doc.get("documentId"),
        "title": doc.get("title"),
        "content": content
    }


def insert_text(docs_service, document_id, text, index=1):
    """Insert text at a specific position."""
    requests = [
        {
            "insertText": {
                "location": {"index": index},
                "text": text
            }
        }
    ]
    docs_service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()
    return f"Inserted text into document"


def append_text(docs_service, document_id, text):
    """Append text to the end of the document."""
    # Get current document length
    doc = docs_service.documents().get(documentId=document_id).execute()
    end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1) - 1

    if end_index < 1:
        end_index = 1

    requests = [
        {
            "insertText": {
                "location": {"index": end_index},
                "text": text
            }
        }
    ]
    docs_service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()
    return "Text appended to document"


def replace_text(docs_service, document_id, old_text, new_text):
    """Replace text in the document."""
    requests = [
        {
            "replaceAllText": {
                "containsText": {
                    "text": old_text,
                    "matchCase": True
                },
                "replaceText": new_text
            }
        }
    ]
    result = docs_service.documents().batchUpdate(
        documentId=document_id, body={"requests": requests}
    ).execute()

    count = result.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    return f"Replaced {count} occurrence(s)"


def list_docs(drive_service, max_results=10):
    """List recent Google Docs."""
    query = "mimeType='application/vnd.google-apps.document' and trashed=false"
    results = drive_service.files().list(
        pageSize=max_results,
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if not files:
        return "No documents found."

    output = f"\nYour documents ({len(files)}):\n"
    for i, f in enumerate(files, 1):
        name = f["name"][:45]
        modified = f.get("modifiedTime", "")[:10]
        output += f"  {i}. {name} (modified: {modified})\n"
    return output


def search_docs(drive_service, query, max_results=10):
    """Search for Google Docs by name."""
    search_query = f"mimeType='application/vnd.google-apps.document' and name contains '{query}' and trashed=false"
    results = drive_service.files().list(
        pageSize=max_results,
        q=search_query,
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    if not files:
        return f"No documents found matching '{query}'."

    output = f"\nFound {len(files)} document(s):\n"
    for i, f in enumerate(files, 1):
        output += f"  {i}. {f['name']}\n"
    return output


def get_doc_by_index(drive_service, index):
    """Get document by index from recent list."""
    query = "mimeType='application/vnd.google-apps.document' and trashed=false"
    results = drive_service.files().list(
        pageSize=20,
        q=query,
        fields="files(id, name)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if index < 1 or index > len(files):
        return None
    return files[index - 1]


def process_with_ai(docs_service, drive_service, user_input):
    """Use AI to understand and execute Docs commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    docs_context = list_docs(drive_service, 5)

    prompt = f"""You are a Google Docs assistant. Today is {today}.

Recent documents:
{docs_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing documents:
{{"action": "list", "count": 10}}

For searching documents:
{{"action": "search", "query": "search term"}}

For creating a new document:
{{"action": "create", "title": "Document Title"}}

For reading document content (by number from list):
{{"action": "read", "index": 1}}

For adding/appending text to a document:
{{"action": "append", "index": 1, "text": "Text to add"}}

For replacing text in a document:
{{"action": "replace", "index": 1, "old_text": "old", "new_text": "new"}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        json_match = re.search(r'\{[^}]+\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "list":
                count = data.get("count", 10)
                return list_docs(drive_service, count)

            elif data.get("action") == "search":
                query = data.get("query", "")
                return search_docs(drive_service, query)

            elif data.get("action") == "create":
                title = data.get("title", "Untitled Document")
                result = create_document(docs_service, title)
                return f"Created '{result['title']}'\nURL: {result['url']}"

            elif data.get("action") == "read":
                index = data.get("index", 1)
                doc_info = get_doc_by_index(drive_service, index)
                if doc_info:
                    doc = get_document(docs_service, doc_info["id"])
                    content = doc["content"][:2000] if len(doc["content"]) > 2000 else doc["content"]
                    return f"\n{doc['title']}\n{'=' * 40}\n{content}"
                return "Could not find that document."

            elif data.get("action") == "append":
                index = data.get("index", 1)
                text = data.get("text", "")
                doc_info = get_doc_by_index(drive_service, index)
                if doc_info and text:
                    return append_text(docs_service, doc_info["id"], text)
                return "Need document and text to append."

            elif data.get("action") == "replace":
                index = data.get("index", 1)
                old_text = data.get("old_text", "")
                new_text = data.get("new_text", "")
                doc_info = get_doc_by_index(drive_service, index)
                if doc_info and old_text:
                    return replace_text(docs_service, doc_info["id"], old_text, new_text)
                return "Need document, old text, and new text."

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Docs Agent")
    print("=" * 50)

    try:
        docs_service = get_docs_service()
        drive_service = get_drive_service()
        print("Connected to Google Docs!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my documents'")
    print("  - 'Create a document called Meeting Notes'")
    print("  - 'Read document 1'")
    print("  - 'Add text to document 2: Action items for today'")
    print("  - 'Find my project proposal'")
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
        if user_input.lower() in ["list", "docs", "documents", "show docs"]:
            print(list_docs(drive_service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(docs_service, drive_service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

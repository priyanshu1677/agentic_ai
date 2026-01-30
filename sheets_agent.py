"""
Google Sheets Agent - Natural language interface for Sheets operations.
Integrates with existing google_sheets_tool functionality.
"""

import json
import re
from datetime import datetime
from google_auth import get_sheets_service, get_drive_service, call_gumloop


def create_spreadsheet(sheets_service, title):
    """Create a new Google Spreadsheet."""
    spreadsheet = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "Sheet1"}}]
    }
    result = sheets_service.spreadsheets().create(body=spreadsheet).execute()
    return {
        "id": result.get("spreadsheetId"),
        "title": result.get("properties", {}).get("title"),
        "url": result.get("spreadsheetUrl")
    }


def read_range(sheets_service, spreadsheet_id, range_name):
    """Read data from a specific range."""
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    return result.get("values", [])


def write_range(sheets_service, spreadsheet_id, range_name, values):
    """Write data to a specific range."""
    body = {"values": values}
    result = sheets_service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()
    return f"Updated {result.get('updatedCells', 0)} cells"


def append_row(sheets_service, spreadsheet_id, range_name, values):
    """Append a row to the spreadsheet."""
    body = {"values": [values]}
    result = sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()
    return f"Appended row to {result.get('updates', {}).get('updatedRange', 'spreadsheet')}"


def clear_range(sheets_service, spreadsheet_id, range_name):
    """Clear data from a range."""
    sheets_service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name
    ).execute()
    return f"Cleared range {range_name}"


def get_spreadsheet_info(sheets_service, spreadsheet_id):
    """Get spreadsheet metadata."""
    result = sheets_service.spreadsheets().get(
        spreadsheetId=spreadsheet_id
    ).execute()

    sheets = []
    for sheet in result.get("sheets", []):
        props = sheet.get("properties", {})
        sheets.append({
            "title": props.get("title"),
            "id": props.get("sheetId"),
            "rows": props.get("gridProperties", {}).get("rowCount", 0),
            "cols": props.get("gridProperties", {}).get("columnCount", 0)
        })

    return {
        "title": result.get("properties", {}).get("title"),
        "id": result.get("spreadsheetId"),
        "url": result.get("spreadsheetUrl"),
        "sheets": sheets
    }


def list_spreadsheets(drive_service, max_results=10):
    """List recent Google Spreadsheets."""
    query = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive_service.files().list(
        pageSize=max_results,
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if not files:
        return "No spreadsheets found."

    output = f"\nYour spreadsheets ({len(files)}):\n"
    for i, f in enumerate(files, 1):
        name = f["name"][:45]
        modified = f.get("modifiedTime", "")[:10]
        output += f"  {i}. {name} (modified: {modified})\n"
    return output


def search_spreadsheets(drive_service, query, max_results=10):
    """Search for spreadsheets by name."""
    search_query = f"mimeType='application/vnd.google-apps.spreadsheet' and name contains '{query}' and trashed=false"
    results = drive_service.files().list(
        pageSize=max_results,
        q=search_query,
        fields="files(id, name)"
    ).execute()
    files = results.get("files", [])

    if not files:
        return f"No spreadsheets found matching '{query}'."

    output = f"\nFound {len(files)} spreadsheet(s):\n"
    for i, f in enumerate(files, 1):
        output += f"  {i}. {f['name']}\n"
    return output


def get_sheet_by_index(drive_service, index):
    """Get spreadsheet by index from recent list."""
    query = "mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
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


def format_data_as_table(data):
    """Format 2D data as a readable table."""
    if not data:
        return "(Empty)"

    # Calculate column widths
    col_widths = []
    for row in data:
        for i, cell in enumerate(row):
            cell_str = str(cell) if cell else ""
            if i >= len(col_widths):
                col_widths.append(len(cell_str))
            else:
                col_widths[i] = max(col_widths[i], len(cell_str))

    # Cap column widths
    col_widths = [min(w, 20) for w in col_widths]

    output = ""
    for row in data:
        row_str = " | ".join(
            str(cell)[:20].ljust(col_widths[i]) if i < len(col_widths) else str(cell)[:20]
            for i, cell in enumerate(row)
        )
        output += row_str + "\n"
    return output


def process_with_ai(sheets_service, drive_service, user_input):
    """Use AI to understand and execute Sheets commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    sheets_context = list_spreadsheets(drive_service, 5)

    prompt = f"""You are a Google Sheets assistant. Today is {today}.

Recent spreadsheets:
{sheets_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing spreadsheets:
{{"action": "list", "count": 10}}

For searching spreadsheets:
{{"action": "search", "query": "search term"}}

For creating a new spreadsheet:
{{"action": "create", "title": "Spreadsheet Title"}}

For reading data (by spreadsheet number from list):
{{"action": "read", "index": 1, "range": "Sheet1!A1:Z100"}}

For writing/updating data:
{{"action": "write", "index": 1, "range": "A1", "values": [["val1", "val2"], ["val3", "val4"]]}}

For appending a row:
{{"action": "append", "index": 1, "values": ["col1", "col2", "col3"]}}

For getting spreadsheet info:
{{"action": "info", "index": 1}}

For clearing a range:
{{"action": "clear", "index": 1, "range": "A1:C10"}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        # Handle multi-line JSON with values arrays
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "list":
                count = data.get("count", 10)
                return list_spreadsheets(drive_service, count)

            elif data.get("action") == "search":
                query = data.get("query", "")
                return search_spreadsheets(drive_service, query)

            elif data.get("action") == "create":
                title = data.get("title", "Untitled Spreadsheet")
                result = create_spreadsheet(sheets_service, title)
                return f"Created '{result['title']}'\nURL: {result['url']}"

            elif data.get("action") == "read":
                index = data.get("index", 1)
                range_name = data.get("range", "Sheet1!A1:Z100")
                sheet_info = get_sheet_by_index(drive_service, index)
                if sheet_info:
                    data_result = read_range(sheets_service, sheet_info["id"], range_name)
                    if data_result:
                        return f"\n{sheet_info['name']} - {range_name}\n{'=' * 40}\n{format_data_as_table(data_result)}"
                    return f"No data in range {range_name}"
                return "Could not find that spreadsheet."

            elif data.get("action") == "write":
                index = data.get("index", 1)
                range_name = data.get("range", "A1")
                values = data.get("values", [])
                sheet_info = get_sheet_by_index(drive_service, index)
                if sheet_info and values:
                    return write_range(sheets_service, sheet_info["id"], range_name, values)
                return "Need spreadsheet and values to write."

            elif data.get("action") == "append":
                index = data.get("index", 1)
                values = data.get("values", [])
                sheet_info = get_sheet_by_index(drive_service, index)
                if sheet_info and values:
                    return append_row(sheets_service, sheet_info["id"], "Sheet1", values)
                return "Need spreadsheet and values to append."

            elif data.get("action") == "info":
                index = data.get("index", 1)
                sheet_info = get_sheet_by_index(drive_service, index)
                if sheet_info:
                    info = get_spreadsheet_info(sheets_service, sheet_info["id"])
                    output = f"\n{info['title']}\n{'=' * 40}\n"
                    output += f"URL: {info['url']}\n\nSheets:\n"
                    for s in info['sheets']:
                        output += f"  - {s['title']} ({s['rows']} rows, {s['cols']} cols)\n"
                    return output
                return "Could not find that spreadsheet."

            elif data.get("action") == "clear":
                index = data.get("index", 1)
                range_name = data.get("range", "")
                sheet_info = get_sheet_by_index(drive_service, index)
                if sheet_info and range_name:
                    return clear_range(sheets_service, sheet_info["id"], range_name)
                return "Need spreadsheet and range to clear."

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Sheets Agent")
    print("=" * 50)

    try:
        sheets_service = get_sheets_service()
        drive_service = get_drive_service()
        print("Connected to Google Sheets!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my spreadsheets'")
    print("  - 'Create a spreadsheet called Budget 2024'")
    print("  - 'Read data from spreadsheet 1'")
    print("  - 'Add a row: John, 500, January'")
    print("  - 'Find my expenses sheet'")
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
        if user_input.lower() in ["list", "sheets", "spreadsheets", "show sheets"]:
            print(list_spreadsheets(drive_service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(sheets_service, drive_service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

"""
Google Slides Agent - Natural language interface for Slides operations.
"""

import json
import re
from datetime import datetime
from google_auth import get_slides_service, get_drive_service, call_gumloop


def create_presentation(slides_service, title):
    """Create a new Google Slides presentation."""
    presentation = {"title": title}
    result = slides_service.presentations().create(body=presentation).execute()
    return {
        "id": result.get("presentationId"),
        "title": result.get("title"),
        "url": f"https://docs.google.com/presentation/d/{result.get('presentationId')}/edit"
    }


def get_presentation(slides_service, presentation_id):
    """Get presentation details."""
    result = slides_service.presentations().get(
        presentationId=presentation_id
    ).execute()

    slides = []
    for slide in result.get("slides", []):
        slide_info = {"id": slide.get("objectId"), "elements": []}
        for element in slide.get("pageElements", []):
            if "shape" in element and "text" in element.get("shape", {}):
                text_content = ""
                for text_element in element["shape"]["text"].get("textElements", []):
                    if "textRun" in text_element:
                        text_content += text_element["textRun"].get("content", "")
                if text_content.strip():
                    slide_info["elements"].append(text_content.strip())
        slides.append(slide_info)

    return {
        "id": result.get("presentationId"),
        "title": result.get("title"),
        "slides": slides,
        "slide_count": len(slides)
    }


def add_slide(slides_service, presentation_id, layout="BLANK"):
    """Add a new slide to the presentation."""
    requests = [
        {
            "createSlide": {
                "slideLayoutReference": {
                    "predefinedLayout": layout
                }
            }
        }
    ]
    result = slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests}
    ).execute()

    slide_id = result.get("replies", [{}])[0].get("createSlide", {}).get("objectId")
    return f"Added new slide (ID: {slide_id})"


def add_text_to_slide(slides_service, presentation_id, slide_id, text, x=100, y=100, width=400, height=50):
    """Add a text box to a specific slide."""
    # Generate unique element ID
    element_id = f"textbox_{datetime.now().strftime('%H%M%S%f')}"

    requests = [
        {
            "createShape": {
                "objectId": element_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {
                        "width": {"magnitude": width, "unit": "PT"},
                        "height": {"magnitude": height, "unit": "PT"}
                    },
                    "transform": {
                        "scaleX": 1,
                        "scaleY": 1,
                        "translateX": x,
                        "translateY": y,
                        "unit": "PT"
                    }
                }
            }
        },
        {
            "insertText": {
                "objectId": element_id,
                "text": text,
                "insertionIndex": 0
            }
        }
    ]

    slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests}
    ).execute()

    return f"Added text to slide"


def add_title_slide(slides_service, presentation_id, title, subtitle=""):
    """Add a slide with title and subtitle."""
    requests = [
        {
            "createSlide": {
                "slideLayoutReference": {
                    "predefinedLayout": "TITLE"
                }
            }
        }
    ]

    result = slides_service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={"requests": requests}
    ).execute()

    slide_id = result.get("replies", [{}])[0].get("createSlide", {}).get("objectId")

    # Get the slide to find placeholder IDs
    presentation = slides_service.presentations().get(
        presentationId=presentation_id
    ).execute()

    # Find the new slide and its placeholders
    for slide in presentation.get("slides", []):
        if slide.get("objectId") == slide_id:
            for element in slide.get("pageElements", []):
                placeholder = element.get("shape", {}).get("placeholder", {})
                if placeholder.get("type") == "CENTERED_TITLE":
                    title_id = element.get("objectId")
                    requests = [{
                        "insertText": {
                            "objectId": title_id,
                            "text": title,
                            "insertionIndex": 0
                        }
                    }]
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()
                elif placeholder.get("type") == "SUBTITLE" and subtitle:
                    subtitle_id = element.get("objectId")
                    requests = [{
                        "insertText": {
                            "objectId": subtitle_id,
                            "text": subtitle,
                            "insertionIndex": 0
                        }
                    }]
                    slides_service.presentations().batchUpdate(
                        presentationId=presentation_id,
                        body={"requests": requests}
                    ).execute()

    return f"Added title slide: '{title}'"


def list_presentations(drive_service, max_results=10):
    """List recent Google Slides presentations."""
    query = "mimeType='application/vnd.google-apps.presentation' and trashed=false"
    results = drive_service.files().list(
        pageSize=max_results,
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if not files:
        return "No presentations found."

    output = f"\nYour presentations ({len(files)}):\n"
    for i, f in enumerate(files, 1):
        name = f["name"][:45]
        modified = f.get("modifiedTime", "")[:10]
        output += f"  {i}. {name} (modified: {modified})\n"
    return output


def get_presentation_by_index(drive_service, index):
    """Get presentation by index from recent list."""
    query = "mimeType='application/vnd.google-apps.presentation' and trashed=false"
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


def process_with_ai(slides_service, drive_service, user_input):
    """Use AI to understand and execute Slides commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    slides_context = list_presentations(drive_service, 5)

    prompt = f"""You are a Google Slides assistant. Today is {today}.

Recent presentations:
{slides_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing presentations:
{{"action": "list", "count": 10}}

For creating a new presentation:
{{"action": "create", "title": "Presentation Title"}}

For getting presentation info (by number from list):
{{"action": "info", "index": 1}}

For adding a blank slide:
{{"action": "add_slide", "index": 1}}

For adding a title slide:
{{"action": "add_title", "index": 1, "title": "Slide Title", "subtitle": "Optional subtitle"}}

For adding text to a slide:
{{"action": "add_text", "index": 1, "slide_num": 1, "text": "Text content"}}

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
                return list_presentations(drive_service, count)

            elif data.get("action") == "create":
                title = data.get("title", "Untitled Presentation")
                result = create_presentation(slides_service, title)
                return f"Created '{result['title']}'\nURL: {result['url']}"

            elif data.get("action") == "info":
                index = data.get("index", 1)
                pres_info = get_presentation_by_index(drive_service, index)
                if pres_info:
                    pres = get_presentation(slides_service, pres_info["id"])
                    output = f"\n{pres['title']}\n{'=' * 40}\n"
                    output += f"Slides: {pres['slide_count']}\n\n"
                    for i, slide in enumerate(pres['slides'], 1):
                        output += f"Slide {i}:\n"
                        for elem in slide['elements'][:3]:
                            output += f"  - {elem[:50]}...\n" if len(elem) > 50 else f"  - {elem}\n"
                    return output
                return "Could not find that presentation."

            elif data.get("action") == "add_slide":
                index = data.get("index", 1)
                pres_info = get_presentation_by_index(drive_service, index)
                if pres_info:
                    return add_slide(slides_service, pres_info["id"])
                return "Could not find that presentation."

            elif data.get("action") == "add_title":
                index = data.get("index", 1)
                title = data.get("title", "Title")
                subtitle = data.get("subtitle", "")
                pres_info = get_presentation_by_index(drive_service, index)
                if pres_info:
                    return add_title_slide(slides_service, pres_info["id"], title, subtitle)
                return "Could not find that presentation."

            elif data.get("action") == "add_text":
                index = data.get("index", 1)
                slide_num = data.get("slide_num", 1) - 1  # Convert to 0-indexed
                text = data.get("text", "")
                pres_info = get_presentation_by_index(drive_service, index)
                if pres_info and text:
                    pres = get_presentation(slides_service, pres_info["id"])
                    if slide_num < len(pres['slides']):
                        slide_id = pres['slides'][slide_num]['id']
                        return add_text_to_slide(slides_service, pres_info["id"], slide_id, text)
                    return f"Slide {slide_num + 1} not found. Presentation has {len(pres['slides'])} slides."
                return "Need presentation and text."

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Slides Agent")
    print("=" * 50)

    try:
        slides_service = get_slides_service()
        drive_service = get_drive_service()
        print("Connected to Google Slides!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my presentations'")
    print("  - 'Create a presentation called Q1 Report'")
    print("  - 'Add a slide with title Summary'")
    print("  - 'How many slides in presentation 1?'")
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
        if user_input.lower() in ["list", "slides", "presentations", "show presentations"]:
            print(list_presentations(drive_service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(slides_service, drive_service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

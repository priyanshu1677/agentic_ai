"""
Google Forms Agent - Natural language interface for Forms operations.
"""

import json
import re
from datetime import datetime
from google_auth import get_forms_service, get_drive_service, call_gumloop


def create_form(forms_service, title):
    """Create a new Google Form."""
    form = {
        "info": {
            "title": title,
            "documentTitle": title
        }
    }
    result = forms_service.forms().create(body=form).execute()
    return {
        "id": result.get("formId"),
        "title": result.get("info", {}).get("title"),
        "url": result.get("responderUri"),
        "edit_url": f"https://docs.google.com/forms/d/{result.get('formId')}/edit"
    }


def get_form(forms_service, form_id):
    """Get form details."""
    result = forms_service.forms().get(formId=form_id).execute()

    questions = []
    for item in result.get("items", []):
        q_info = item.get("questionItem", {}).get("question", {})
        questions.append({
            "id": item.get("itemId"),
            "title": item.get("title", "Untitled question"),
            "type": q_info.get("textQuestion", q_info.get("choiceQuestion", {}))
        })

    return {
        "id": result.get("formId"),
        "title": result.get("info", {}).get("title"),
        "description": result.get("info", {}).get("description", ""),
        "questions": questions,
        "question_count": len(questions)
    }


def add_question(forms_service, form_id, question_text, question_type="SHORT_TEXT", choices=None):
    """Add a question to the form."""
    question_item = {
        "title": question_text
    }

    if question_type == "SHORT_TEXT":
        question_item["questionItem"] = {
            "question": {
                "required": False,
                "textQuestion": {
                    "paragraph": False
                }
            }
        }
    elif question_type == "PARAGRAPH":
        question_item["questionItem"] = {
            "question": {
                "required": False,
                "textQuestion": {
                    "paragraph": True
                }
            }
        }
    elif question_type == "MULTIPLE_CHOICE" and choices:
        question_item["questionItem"] = {
            "question": {
                "required": False,
                "choiceQuestion": {
                    "type": "RADIO",
                    "options": [{"value": c} for c in choices]
                }
            }
        }
    elif question_type == "CHECKBOX" and choices:
        question_item["questionItem"] = {
            "question": {
                "required": False,
                "choiceQuestion": {
                    "type": "CHECKBOX",
                    "options": [{"value": c} for c in choices]
                }
            }
        }
    elif question_type == "SCALE":
        question_item["questionItem"] = {
            "question": {
                "required": False,
                "scaleQuestion": {
                    "low": 1,
                    "high": 5,
                    "lowLabel": "Low",
                    "highLabel": "High"
                }
            }
        }

    request = {
        "requests": [{
            "createItem": {
                "item": question_item,
                "location": {"index": 0}
            }
        }]
    }

    forms_service.forms().batchUpdate(
        formId=form_id,
        body=request
    ).execute()

    return f"Added question: '{question_text}'"


def get_responses(forms_service, form_id, max_results=50):
    """Get form responses."""
    result = forms_service.forms().responses().list(
        formId=form_id,
        pageSize=max_results
    ).execute()

    responses = result.get("responses", [])

    if not responses:
        return "No responses yet."

    output = f"\nForm has {len(responses)} response(s):\n"

    for i, response in enumerate(responses[:10], 1):
        output += f"\nResponse {i}:\n"
        answers = response.get("answers", {})
        for q_id, answer in answers.items():
            text_answers = answer.get("textAnswers", {}).get("answers", [])
            if text_answers:
                output += f"  - {text_answers[0].get('value', 'N/A')}\n"

    return output


def list_forms(drive_service, max_results=10):
    """List recent Google Forms."""
    query = "mimeType='application/vnd.google-apps.form' and trashed=false"
    results = drive_service.files().list(
        pageSize=max_results,
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc"
    ).execute()
    files = results.get("files", [])

    if not files:
        return "No forms found."

    output = f"\nYour forms ({len(files)}):\n"
    for i, f in enumerate(files, 1):
        name = f["name"][:45]
        modified = f.get("modifiedTime", "")[:10]
        output += f"  {i}. {name} (modified: {modified})\n"
    return output


def get_form_by_index(drive_service, index):
    """Get form by index from recent list."""
    query = "mimeType='application/vnd.google-apps.form' and trashed=false"
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


def process_with_ai(forms_service, drive_service, user_input):
    """Use AI to understand and execute Forms commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    forms_context = list_forms(drive_service, 5)

    prompt = f"""You are a Google Forms assistant. Today is {today}.

Recent forms:
{forms_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing forms:
{{"action": "list", "count": 10}}

For creating a new form:
{{"action": "create", "title": "Form Title"}}

For getting form info (by number from list):
{{"action": "info", "index": 1}}

For adding a text question:
{{"action": "add_question", "index": 1, "question": "Question text", "type": "SHORT_TEXT"}}

For adding a paragraph question:
{{"action": "add_question", "index": 1, "question": "Question text", "type": "PARAGRAPH"}}

For adding multiple choice:
{{"action": "add_question", "index": 1, "question": "Question text", "type": "MULTIPLE_CHOICE", "choices": ["Option 1", "Option 2", "Option 3"]}}

For adding checkbox question:
{{"action": "add_question", "index": 1, "question": "Question text", "type": "CHECKBOX", "choices": ["Option 1", "Option 2"]}}

For adding a 1-5 scale question:
{{"action": "add_question", "index": 1, "question": "Rate your experience", "type": "SCALE"}}

For viewing responses:
{{"action": "responses", "index": 1}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Question types: SHORT_TEXT, PARAGRAPH, MULTIPLE_CHOICE, CHECKBOX, SCALE

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "list":
                count = data.get("count", 10)
                return list_forms(drive_service, count)

            elif data.get("action") == "create":
                title = data.get("title", "Untitled Form")
                result = create_form(forms_service, title)
                return f"Created '{result['title']}'\nForm URL: {result['url']}\nEdit URL: {result['edit_url']}"

            elif data.get("action") == "info":
                index = data.get("index", 1)
                form_info = get_form_by_index(drive_service, index)
                if form_info:
                    form = get_form(forms_service, form_info["id"])
                    output = f"\n{form['title']}\n{'=' * 40}\n"
                    if form['description']:
                        output += f"Description: {form['description']}\n"
                    output += f"Questions: {form['question_count']}\n\n"
                    for i, q in enumerate(form['questions'], 1):
                        output += f"  {i}. {q['title']}\n"
                    return output
                return "Could not find that form."

            elif data.get("action") == "add_question":
                index = data.get("index", 1)
                question = data.get("question", "")
                q_type = data.get("type", "SHORT_TEXT")
                choices = data.get("choices")
                form_info = get_form_by_index(drive_service, index)
                if form_info and question:
                    return add_question(forms_service, form_info["id"], question, q_type, choices)
                return "Need form and question text."

            elif data.get("action") == "responses":
                index = data.get("index", 1)
                form_info = get_form_by_index(drive_service, index)
                if form_info:
                    return get_responses(forms_service, form_info["id"])
                return "Could not find that form."

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Forms Agent")
    print("=" * 50)

    try:
        forms_service = get_forms_service()
        drive_service = get_drive_service()
        print("Connected to Google Forms!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my forms'")
    print("  - 'Create a feedback form'")
    print("  - 'Add question to form 1: What is your name?'")
    print("  - 'Add multiple choice: Rate 1-5'")
    print("  - 'Show responses to form 1'")
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
        if user_input.lower() in ["list", "forms", "show forms", "my forms"]:
            print(list_forms(drive_service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(forms_service, drive_service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

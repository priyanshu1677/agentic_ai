"""
Google Tasks Agent - Natural language interface for Tasks operations.
"""

import json
import re
from datetime import datetime, timedelta
from google_auth import get_tasks_service, call_gumloop


def list_task_lists(service):
    """List all task lists."""
    results = service.tasklists().list().execute()
    tasklists = results.get("items", [])

    if not tasklists:
        return "No task lists found.", []

    output = "\nYour task lists:\n"
    for i, tl in enumerate(tasklists, 1):
        output += f"  {i}. {tl['title']}\n"

    return output, tasklists


def list_tasks(service, tasklist_id="@default", show_completed=False):
    """List tasks in a task list."""
    results = service.tasks().list(
        tasklist=tasklist_id,
        showCompleted=show_completed,
        showHidden=show_completed
    ).execute()
    tasks = results.get("items", [])

    if not tasks:
        return "No tasks found."

    output = f"\nYour tasks ({len(tasks)}):\n"
    for i, task in enumerate(tasks, 1):
        title = task.get("title", "Untitled")[:40]
        status = "Done" if task.get("status") == "completed" else "Pending"
        due = task.get("due", "")[:10] if task.get("due") else ""
        due_str = f" (due: {due})" if due else ""
        status_icon = "[x]" if status == "Done" else "[ ]"
        output += f"  {i}. {status_icon} {title}{due_str}\n"

    return output


def create_task(service, title, notes="", due_date=None, tasklist_id="@default"):
    """Create a new task."""
    task = {"title": title}

    if notes:
        task["notes"] = notes

    if due_date:
        # Format as RFC 3339 timestamp
        task["due"] = f"{due_date}T00:00:00.000Z"

    result = service.tasks().insert(
        tasklist=tasklist_id,
        body=task
    ).execute()

    return f"Created task: '{result.get('title')}'"


def complete_task(service, task_id, tasklist_id="@default"):
    """Mark a task as completed."""
    task = service.tasks().get(
        tasklist=tasklist_id,
        task=task_id
    ).execute()

    task["status"] = "completed"
    service.tasks().update(
        tasklist=tasklist_id,
        task=task_id,
        body=task
    ).execute()

    return f"Completed: '{task.get('title')}'"


def delete_task(service, task_id, tasklist_id="@default"):
    """Delete a task."""
    service.tasks().delete(
        tasklist=tasklist_id,
        task=task_id
    ).execute()

    return "Task deleted."


def clear_completed(service, tasklist_id="@default"):
    """Clear all completed tasks."""
    service.tasks().clear(tasklist=tasklist_id).execute()
    return "Cleared all completed tasks."


def create_task_list(service, title):
    """Create a new task list."""
    tasklist = {"title": title}
    result = service.tasklists().insert(body=tasklist).execute()
    return f"Created task list: '{result.get('title')}'"


def get_task_by_index(service, index, tasklist_id="@default"):
    """Get task by index from the list."""
    results = service.tasks().list(
        tasklist=tasklist_id,
        showCompleted=True
    ).execute()
    tasks = results.get("items", [])

    if index < 1 or index > len(tasks):
        return None
    return tasks[index - 1]


def get_task_by_title(service, title, tasklist_id="@default"):
    """Find task by title (partial match)."""
    results = service.tasks().list(
        tasklist=tasklist_id,
        showCompleted=True
    ).execute()
    tasks = results.get("items", [])

    title_lower = title.lower()
    for task in tasks:
        if title_lower in task.get("title", "").lower():
            return task
    return None


def parse_due_date(text):
    """Parse natural language date."""
    today = datetime.now()

    if "today" in text.lower():
        return today.strftime("%Y-%m-%d")
    elif "tomorrow" in text.lower():
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "next week" in text.lower():
        return (today + timedelta(days=7)).strftime("%Y-%m-%d")

    # Check for "in X days"
    match = re.search(r'in\s*(\d+)\s*day', text.lower())
    if match:
        days = int(match.group(1))
        return (today + timedelta(days=days)).strftime("%Y-%m-%d")

    # Check for explicit date
    match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if match:
        return match.group(1)

    return None


def process_with_ai(service, user_input):
    """Use AI to understand and execute Tasks commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    tasks_context = list_tasks(service)

    prompt = f"""You are a Google Tasks assistant. Today is {today}.

Current tasks:
{tasks_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing tasks:
{{"action": "list"}}

For listing completed tasks too:
{{"action": "list_all"}}

For creating a task:
{{"action": "create", "title": "Task title", "notes": "optional notes", "due": "YYYY-MM-DD or null"}}

For completing a task (by number from list or partial title):
{{"action": "complete", "index": 1}}
OR
{{"action": "complete", "title": "partial task title"}}

For deleting a task:
{{"action": "delete", "index": 1}}

For clearing completed tasks:
{{"action": "clear_completed"}}

For listing task lists:
{{"action": "list_lists"}}

For creating a task list:
{{"action": "create_list", "title": "List name"}}

For general questions:
{{"action": "chat", "response": "your helpful response"}}

Date formats: "today", "tomorrow", "in 3 days", "YYYY-MM-DD"

Only respond with the JSON, nothing else."""

    ai_response = call_gumloop(prompt)

    try:
        json_match = re.search(r'\{[^}]+\}', ai_response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())

            if data.get("action") == "list":
                return list_tasks(service)

            elif data.get("action") == "list_all":
                return list_tasks(service, show_completed=True)

            elif data.get("action") == "create":
                title = data.get("title", "")
                notes = data.get("notes", "")
                due = data.get("due")
                if title:
                    return create_task(service, title, notes, due)
                return "Need a task title."

            elif data.get("action") == "complete":
                if "index" in data:
                    task = get_task_by_index(service, data["index"])
                elif "title" in data:
                    task = get_task_by_title(service, data["title"])
                else:
                    return "Need task index or title to complete."

                if task:
                    return complete_task(service, task["id"])
                return "Could not find that task."

            elif data.get("action") == "delete":
                index = data.get("index", 1)
                task = get_task_by_index(service, index)
                if task:
                    return delete_task(service, task["id"])
                return "Could not find that task."

            elif data.get("action") == "clear_completed":
                return clear_completed(service)

            elif data.get("action") == "list_lists":
                output, _ = list_task_lists(service)
                return output

            elif data.get("action") == "create_list":
                title = data.get("title", "New List")
                return create_task_list(service, title)

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Tasks Agent")
    print("=" * 50)

    try:
        service = get_tasks_service()
        print("Connected to Google Tasks!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my tasks'")
    print("  - 'Add task: Buy groceries'")
    print("  - 'Add task: Call mom, due tomorrow'")
    print("  - 'Mark task 1 as done'")
    print("  - 'Complete the groceries task'")
    print("  - 'Delete task 2'")
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
        if user_input.lower() in ["list", "tasks", "show tasks", "my tasks"]:
            print(list_tasks(service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

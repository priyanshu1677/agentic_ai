# Google Workspace Integration Suite

A complete suite of AI-powered agents for interacting with Google Workspace services using natural language.

## Features

- **9 Google Services** integrated with natural language processing
- **Unified Interface** - Single agent to control all services
- **Gumloop AI** - Natural language understanding for commands
- **OAuth Authentication** - Secure, one-time setup for all services

## Supported Services

| Service | Agent | Description |
|---------|-------|-------------|
| Calendar | `calendar_agent.py` | Create, list, delete events |
| Gmail | `gmail_agent.py` | Send, read, search emails |
| Drive | `drive_agent.py` | Upload, download, share files |
| Docs | `docs_agent.py` | Create, read, edit documents |
| Sheets | `sheets_agent.py` | Read, write, append spreadsheet data |
| Slides | `slides_agent.py` | Create presentations, add slides |
| Tasks | `tasks_agent.py` | Create, complete, delete tasks |
| Contacts | `contacts_agent.py` | List, search, create contacts |
| Forms | `forms_agent.py` | Create forms, add questions, view responses |
| **All-in-One** | `workspace_agent.py` | Unified interface for all services |

## Quick Start

### 1. Setup Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project
3. Enable these APIs:
   - Google Calendar API
   - Gmail API
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Google Slides API
   - Google Tasks API
   - People API
   - Google Forms API

4. Create OAuth credentials (Desktop app)
5. Download `credentials.json` to this folder

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Agent

```bash
cd ~/Desktop/PROJECTS/agentic_ai

# Unified agent (recommended)
python3 workspace_agent.py

# Or individual agents
python3 gmail_agent.py
python3 calendar_agent.py
python3 sheets_agent.py
```

First run will open a browser for OAuth authentication.

## Usage Examples

### Unified Workspace Agent
```
You: show my calendar
You: send email to john@example.com about the meeting
You: create a spreadsheet called Budget 2024
You: add task: Buy groceries due tomorrow
You: show unread emails
You: status
```

### Individual Agents

**Calendar:**
```
You: show my events
You: schedule meeting tomorrow called Team Standup
You: delete the Team Standup event
```

**Gmail:**
```
You: show unread emails
You: search for emails from Amazon
You: send email to jane@example.com about project update
```

**Sheets:**
```
You: show my spreadsheets
You: create spreadsheet called Expenses
You: read data from spreadsheet 1
You: add row: John, 500, January
```

**Tasks:**
```
You: show my tasks
You: add task: Call mom
You: mark task 1 as done
You: delete completed tasks
```

## File Structure

```
agentic_ai/
├── google_auth.py          # Shared OAuth + Gumloop AI helper
├── workspace_agent.py      # Unified interface (all services)
├── calendar_agent.py       # Calendar operations
├── gmail_agent.py          # Email operations
├── drive_agent.py          # File management
├── docs_agent.py           # Google Docs
├── sheets_agent.py         # Spreadsheets
├── slides_agent.py         # Presentations
├── tasks_agent.py          # To-do lists
├── contacts_agent.py       # Contacts/People
├── forms_agent.py          # Google Forms
├── credentials.json        # OAuth client config (from Google Cloud)
├── token.json              # Saved auth token (auto-generated)
├── requirements.txt        # Python dependencies
└── README.md               # This file
```

## Architecture

```
User Input (Natural Language)
        │
        ▼
┌─────────────────────────┐
│   workspace_agent.py    │  ← Routes to correct service
└───────────┬─────────────┘
            │
    ┌───────┼───────┐
    ▼       ▼       ▼
 Gmail   Calendar  Drive  ... (9 agents)
    │       │       │
    └───────┼───────┘
            ▼
┌─────────────────────────┐
│    google_auth.py       │  ← Shared OAuth + Gumloop AI
└───────────┬─────────────┘
            │
    ┌───────┴───────┐
    ▼               ▼
Google APIs    Gumloop AI
```

## Requirements

- Python 3.9+
- Google Cloud Project with APIs enabled
- OAuth credentials (`credentials.json`)
- Gumloop API access (for AI processing)

## Dependencies

```
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
python-dotenv
requests
```

## License

MIT

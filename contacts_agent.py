"""
Google Contacts Agent - Natural language interface for Contacts operations.
Uses Google People API.
"""

import json
import re
from datetime import datetime
from google_auth import get_people_service, call_gumloop


def list_contacts(service, max_results=10):
    """List contacts."""
    results = service.people().connections().list(
        resourceName="people/me",
        pageSize=max_results,
        personFields="names,emailAddresses,phoneNumbers"
    ).execute()
    connections = results.get("connections", [])

    if not connections:
        return "No contacts found."

    output = f"\nYour contacts ({len(connections)}):\n"
    for i, person in enumerate(connections, 1):
        name = "Unknown"
        if person.get("names"):
            name = person["names"][0].get("displayName", "Unknown")

        email = ""
        if person.get("emailAddresses"):
            email = person["emailAddresses"][0].get("value", "")

        phone = ""
        if person.get("phoneNumbers"):
            phone = person["phoneNumbers"][0].get("value", "")

        contact_info = name
        if email:
            contact_info += f" <{email}>"
        if phone:
            contact_info += f" | {phone}"

        output += f"  {i}. {contact_info}\n"

    return output


def search_contacts(service, query, max_results=10):
    """Search for contacts."""
    results = service.people().searchContacts(
        query=query,
        pageSize=max_results,
        readMask="names,emailAddresses,phoneNumbers"
    ).execute()
    contacts = results.get("results", [])

    if not contacts:
        return f"No contacts found matching '{query}'."

    output = f"\nFound {len(contacts)} contact(s) matching '{query}':\n"
    for i, result in enumerate(contacts, 1):
        person = result.get("person", {})
        name = "Unknown"
        if person.get("names"):
            name = person["names"][0].get("displayName", "Unknown")

        email = ""
        if person.get("emailAddresses"):
            email = person["emailAddresses"][0].get("value", "")

        phone = ""
        if person.get("phoneNumbers"):
            phone = person["phoneNumbers"][0].get("value", "")

        contact_info = name
        if email:
            contact_info += f" <{email}>"
        if phone:
            contact_info += f" | {phone}"

        output += f"  {i}. {contact_info}\n"

    return output


def create_contact(service, name, email=None, phone=None):
    """Create a new contact."""
    contact = {
        "names": [{"givenName": name}]
    }

    if email:
        contact["emailAddresses"] = [{"value": email}]

    if phone:
        contact["phoneNumbers"] = [{"value": phone}]

    result = service.people().createContact(body=contact).execute()
    return f"Created contact: {name}"


def get_contact_details(service, resource_name):
    """Get detailed info for a contact."""
    person = service.people().get(
        resourceName=resource_name,
        personFields="names,emailAddresses,phoneNumbers,organizations,addresses,birthdays"
    ).execute()

    details = {}

    if person.get("names"):
        details["name"] = person["names"][0].get("displayName", "Unknown")

    if person.get("emailAddresses"):
        details["emails"] = [e.get("value") for e in person["emailAddresses"]]

    if person.get("phoneNumbers"):
        details["phones"] = [p.get("value") for p in person["phoneNumbers"]]

    if person.get("organizations"):
        details["organizations"] = [
            o.get("name", "") + (" - " + o.get("title", "") if o.get("title") else "")
            for o in person["organizations"]
        ]

    return details


def update_contact(service, resource_name, email=None, phone=None):
    """Update a contact's email or phone."""
    # Get current contact
    person = service.people().get(
        resourceName=resource_name,
        personFields="names,emailAddresses,phoneNumbers"
    ).execute()

    update_fields = []

    if email:
        person["emailAddresses"] = [{"value": email}]
        update_fields.append("emailAddresses")

    if phone:
        person["phoneNumbers"] = [{"value": phone}]
        update_fields.append("phoneNumbers")

    if not update_fields:
        return "No fields to update."

    result = service.people().updateContact(
        resourceName=resource_name,
        updatePersonFields=",".join(update_fields),
        body=person
    ).execute()

    name = result.get("names", [{}])[0].get("displayName", "Contact")
    return f"Updated {name}"


def delete_contact(service, resource_name):
    """Delete a contact."""
    service.people().deleteContact(resourceName=resource_name).execute()
    return "Contact deleted."


def get_contact_by_index(service, index):
    """Get contact by index from list."""
    results = service.people().connections().list(
        resourceName="people/me",
        pageSize=50,
        personFields="names,emailAddresses,phoneNumbers"
    ).execute()
    connections = results.get("connections", [])

    if index < 1 or index > len(connections):
        return None
    return connections[index - 1]


def get_contact_by_name(service, name):
    """Find contact by name (search)."""
    results = service.people().searchContacts(
        query=name,
        pageSize=1,
        readMask="names,emailAddresses,phoneNumbers"
    ).execute()
    contacts = results.get("results", [])

    if contacts:
        return contacts[0].get("person")
    return None


def process_with_ai(service, user_input):
    """Use AI to understand and execute Contacts commands."""

    today = datetime.now().strftime("%Y-%m-%d")
    contacts_context = list_contacts(service, 5)

    prompt = f"""You are a Google Contacts assistant. Today is {today}.

Recent contacts:
{contacts_context}

User request: "{user_input}"

Analyze the request and respond with ONE of these JSON formats:

For listing contacts:
{{"action": "list", "count": 10}}

For searching contacts:
{{"action": "search", "query": "search name or email"}}

For creating a contact:
{{"action": "create", "name": "Full Name", "email": "email@example.com", "phone": "123-456-7890"}}

For getting contact details (by number from list or name):
{{"action": "details", "index": 1}}
OR
{{"action": "details", "name": "contact name"}}

For updating a contact:
{{"action": "update", "index": 1, "email": "new@email.com", "phone": "new phone"}}

For deleting a contact (by number):
{{"action": "delete", "index": 1}}

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
                return list_contacts(service, count)

            elif data.get("action") == "search":
                query = data.get("query", "")
                return search_contacts(service, query)

            elif data.get("action") == "create":
                name = data.get("name", "")
                email = data.get("email")
                phone = data.get("phone")
                if name:
                    return create_contact(service, name, email, phone)
                return "Need a name to create contact."

            elif data.get("action") == "details":
                contact = None
                if "index" in data:
                    contact = get_contact_by_index(service, data["index"])
                elif "name" in data:
                    contact = get_contact_by_name(service, data["name"])

                if contact:
                    resource_name = contact.get("resourceName")
                    details = get_contact_details(service, resource_name)
                    output = f"\n{details.get('name', 'Unknown')}\n{'=' * 30}\n"
                    if details.get("emails"):
                        output += f"Email: {', '.join(details['emails'])}\n"
                    if details.get("phones"):
                        output += f"Phone: {', '.join(details['phones'])}\n"
                    if details.get("organizations"):
                        output += f"Org: {', '.join(details['organizations'])}\n"
                    return output
                return "Could not find that contact."

            elif data.get("action") == "update":
                index = data.get("index", 1)
                email = data.get("email")
                phone = data.get("phone")
                contact = get_contact_by_index(service, index)
                if contact:
                    return update_contact(service, contact["resourceName"], email, phone)
                return "Could not find that contact."

            elif data.get("action") == "delete":
                index = data.get("index", 1)
                contact = get_contact_by_index(service, index)
                if contact:
                    name = contact.get("names", [{}])[0].get("displayName", "Contact")
                    delete_contact(service, contact["resourceName"])
                    return f"Deleted {name}"
                return "Could not find that contact."

            elif data.get("action") == "chat":
                return data.get("response", ai_response)

        return ai_response
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    print("=" * 50)
    print("Google Contacts Agent")
    print("=" * 50)

    try:
        service = get_people_service()
        print("Connected to Google Contacts!\n")
    except FileNotFoundError:
        print("ERROR: credentials.json not found")
        return
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print("Talk to me naturally! Examples:")
    print("  - 'Show my contacts'")
    print("  - 'Find John's phone number'")
    print("  - 'Add contact: Jane Doe, jane@email.com'")
    print("  - 'Update contact 1 with new email test@email.com'")
    print("  - 'Delete contact 3'")
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
        if user_input.lower() in ["list", "contacts", "show contacts", "my contacts"]:
            print(list_contacts(service))
            continue

        # Use AI for everything else
        print("Thinking...")
        response = process_with_ai(service, user_input)
        print(f"\nAssistant: {response}\n")


if __name__ == "__main__":
    main()

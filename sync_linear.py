import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LINEAR_API_KEY")
TEAM_ID = os.getenv("LINEAR_TEAM_ID")
URL = "https://api.linear.app/graphql"
TODO_FILE = "TODO.md"

if not API_KEY:
    print("Error: LINEAR_API_KEY or LINEAR_TEAM_ID not found in .env")
    exit(1)

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

def graphql_query(query, variables=None):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(URL, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"GraphQL request failed: {response.status_code} {response.text}")
    return response.json()

def fetch_active_issues():
    query = """
    query {
      issues(first: 50, filter: { state: { name: { neq: "Done" } } }) {
        nodes {
          id
          identifier
          title
          priorityLabel
          dueDate
          state {
            name
          }
          assignee {
            name
          }
          project {
            name
          }
          url
        }
      }
    }
    """
    data = graphql_query(query)
    return data.get("data", {}).get("issues", {}).get("nodes", [])

def update_todo_file(issues):
    print(f"Syncing {len(issues)} issues to {TODO_FILE}...")
    
    # Read existing content to preserve header or manual sections if needed
    # For now, we will regenerate the "Active Issues" section
    
    new_lines = []
    
    # Header
    new_lines.append("# TODO List")
    new_lines.append("")
    new_lines.append("This file is synchronized with Linear. Do not remove the ID tags (e.g. [PAC-123]).")
    new_lines.append("")
    new_lines.append("## Active Issues")
    new_lines.append("")
    
    # Sort issues by identifier for stability
    # Or by priority? Let's do Identifier desc for now (newest first)
    sorted_issues = sorted(issues, key=lambda x: x['identifier'], reverse=True)
    
    for issue in sorted_issues:
        ident = issue['identifier'] # e.g. PAC-1
        title = issue['title']
        state = issue['state']['name']
        assignee = issue['assignee']['name'] if issue['assignee'] else "Unassigned"
        url = issue['url']
        priority = issue['priorityLabel']
        project = issue['project']['name'] if issue['project'] else "No Project"
        
        # Format: - [ ] [PAC-123](url) Title (State, Assignee)
        checkbox = "[x]" if state.lower() in ["done", "canceled"] else "[ ]"
        
        line = f"- {checkbox} [{ident}]({url}) **{title}**"
        meta = []
        if state: meta.append(f"State: {state}")
        if priority: meta.append(f"Priority: {priority}")
        if assignee != "Unassigned": meta.append(f"Assignee: {assignee}")
        if project: meta.append(f"Project: {project}")
        
        if meta:
            line += f" <br> *({', '.join(meta)})*"
            
        new_lines.append(line)

    with open(TODO_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))
        
    print(f"Successfully updated {TODO_FILE}")

if __name__ == "__main__":
    current_issues = fetch_active_issues()
    update_todo_file(current_issues)

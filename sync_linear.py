import os
import re
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LINEAR_API_KEY")
TEAM_ID = os.getenv("LINEAR_TEAM_ID")
URL = "https://api.linear.app/graphql"

if not API_KEY or not TEAM_ID:
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

def get_projects():
    query = """
    query {
        projects {
            nodes {
                id
                name
            }
        }
    }
    """
    data = graphql_query(query)
    projects = {}
    for node in data["data"]["projects"]["nodes"]:
        projects[node["name"]] = node["id"]
    return projects

def create_issue(title, description, priority_label, project_id, team_id):
    # Map priority text to Linear priority if needed (0=No Priority, 1=Urgent, 2=High, 3=Normal, 4=Low)
    # Mapping "즉시" -> 1 (Urgent), "단기" -> 2 (High), "중기" -> 3 (Normal), "장기" -> 4 (Low)
    priority_map = {
        "즉시": 1,
        "단기": 2,
        "중기": 3,
        "장기": 4
    }
    priority = priority_map.get(priority_label, 0)

    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue {
                id
                identifier
                url
            }
        }
    }
    """
    variables = {
        "input": {
            "teamId": team_id,
            "title": title,
            "description": description,
            "priority": priority,
            "projectId": project_id,
            "stateId": "86d95f18-b3e0-40d5-823b-8fd24245548e" # Force Todo State
        }
    }
    
    result = graphql_query(mutation, variables)
    if result.get("data") and result["data"]["issueCreate"]["success"]:
        return result["data"]["issueCreate"]["issue"]
    else:
        print(f"Failed to create issue: {json.dumps(result)}")
        return None

def create_meeting_issue(title, content, project_id, team_id):
    # Backlog State ID: 125d3460-81be-4f22-b523-5017c318df22
    backlog_state_id = "125d3460-81be-4f22-b523-5017c318df22"
    
    # 1. Search if issue already exists to avoid duplicates
    # Using a simple search query or filter is hard via GraphQL without complexity.
    # For now, we will just CREATE. Users can delete duplicates or we can refine later.
    # (Checking existence requires implementing search logic, let's keep it simple first
    # or assume the user manages duplicates manually if they re-run often. 
    # actually, we can try to search by title if needed, but let's just create for now to match prompt "create")
    
    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue {
                id
                identifier
                url
            }
        }
    }
    """
    
    variables = {
        "input": {
            "teamId": team_id,
            "title": title,
            "description": content,
            "projectId": project_id,
            "stateId": backlog_state_id
        }
    }
    
    result = graphql_query(mutation, variables)
    if result.get("data") and result["data"]["issueCreate"]["success"]:
        return result["data"]["issueCreate"]["issue"]
    else:
        print(f"Failed to create meeting issue: {json.dumps(result)}")
        return None

def sync_meeting_notes(file_path):
    print(f"Processing {file_path}...")
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    projects_map = get_projects()
    print(f"Found {len(projects_map)} projects from Linear.")
    
    # 1. Create Meeting Note Issue (Backlog)
    target_project_name = "Operations & Infra" 
    target_project_id = projects_map.get(target_project_name)
    
    if target_project_id:
        filename = os.path.basename(file_path).replace(".md", "")
        issue_title = f"[Meeting Notes] {filename}"
        
        print(f"Creating Backlog Issue '{issue_title}'...")
        issue = create_meeting_issue(issue_title, content, target_project_id, TEAM_ID)
        
        if issue:
            print(f"  -> Meeting Issue Created: {issue['url']}")
        else:
            print("  -> Meeting Issue creation failed.")
    else:
        print(f"Warning: Target project '{target_project_name}' not found.")

    lines = content.split('\n')
    table_start_index = -1
    
    # Find the header line
    for i, line in enumerate(lines):
        if "| Project" in line and "Linear Link" in line:
            table_start_index = i
            break
            
    if table_start_index == -1:
        print("No Action Items table found.")
        return

    print(f"Found table header at line {table_start_index}")

    # Collect table lines
    table_lines = []
    current_index = table_start_index
    
    while current_index < len(lines):
        line = lines[current_index]
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        table_lines.append(line)
        current_index += 1
        
    print(f"Debug: Captured {len(table_lines)} lines.")
    
    projects_map = get_projects()
    print(f"Found {len(projects_map)} projects from Linear.")

    # Process lines
    new_table_lines = table_lines[:2] # Header and separator
    updated_count = 0
    
    # Header is index 0, Separator is index 1
    # Data starts index 2
    for line in table_lines[2:]:
        # logic same as before...
        if not line.strip(): 
            continue
            
        parts = [p.strip() for p in line.split('|')]
        
        print(f"Debug: Line parts len={len(parts)}, Project='{parts[1] if len(parts)>1 else 'N/A'}'")
        
        if len(parts) < 7:
            new_table_lines.append(line)
            continue
            
        project_name = parts[1]
        priority = parts[2]
        item = parts[3]
        desc = parts[4]
        due = parts[5]
        link = parts[6]
        
        clean_project_name = project_name.replace("**", "").strip()
        
        if link:
            new_table_lines.append(line)
            continue
            
        print(f"Creating issue for: [{clean_project_name}] {item}")
        
        project_id = projects_map.get(clean_project_name)
        
        if not project_id:
            print(f"Warning: Project '{clean_project_name}' not found in Linear. skipping.")
            new_table_lines.append(line)
            continue

        full_description = f"{desc}\\n\\n**Due Date**: {due}\\n**Source**: Meeting Notes"
        
        issue = create_issue(item, full_description, priority, project_id, TEAM_ID)
        
        if issue:
            new_link = f"[{issue['identifier']}]({issue['url']})"
            parts[6] = " " + new_link + " "
            new_line = " | ".join(parts)
            new_table_lines.append(new_line)
            updated_count += 1
            print(f"  -> Created {issue['identifier']}")
        else:
            new_table_lines.append(line)

    if updated_count > 0:
        # Reconstruct the content
        # We need to replace lines[table_start_index : table_start_index + len(table_lines)]
        
        # Careful with indices. 
        # table_lines has 'len(table_lines)' lines.
        # It corresponds to lines[table_start_index : current_index] in original 'lines' list
        # (since current_index incremented until break)
        
        lines[table_start_index : current_index] = new_table_lines
        
        new_content = "\n".join(lines)
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        print(f"Updated {file_path} with {updated_count} new Linear links.")
    else:
        print("No new issues created.")

if __name__ == "__main__":
    # In a real scenario, we might scan for the latest file
    # For now, hardcode the specific file user is working on
    target_file = "meeting_notes/2026-01-02.md"
    sync_meeting_notes(target_file)

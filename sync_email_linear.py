#!/usr/bin/env python3
"""
Email Notes to Linear Issue Sync Script

Syncs markdown files from email_notes/ folder to Linear as Issues (Backlog).
- Creates new Issues for files without Linear Issue links
- Updates existing Issues for files with Linear Issue links
- Automatically adds Linear Issue URL to the markdown file
"""

import os
import re
import glob
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LINEAR_API_KEY")
TEAM_ID = os.getenv("LINEAR_TEAM_ID") # Should be set in .env or fetched
URL = "https://api.linear.app/graphql"
EMAIL_NOTES_DIR = "email_notes"

if not API_KEY:
    print("Error: LINEAR_API_KEY not found in .env")
    exit(1)

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}


def graphql_query(query, variables=None):
    """Execute a GraphQL query/mutation."""
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    response = requests.post(URL, headers=headers, json=payload)
    if response.status_code != 200:
        raise Exception(f"GraphQL request failed: {response.status_code} {response.text}")
    result = response.json()
    if "errors" in result:
        raise Exception(f"GraphQL errors: {result['errors']}")
    return result


def get_team_id():
    """Fetch the first team ID if not set in .env."""
    global TEAM_ID
    if TEAM_ID:
        return TEAM_ID
    
    query = """
    query {
      teams(first: 1) {
        nodes {
          id
          name
        }
      }
    }
    """
    data = graphql_query(query)
    teams = data.get("data", {}).get("teams", {}).get("nodes", [])
    if teams:
        TEAM_ID = teams[0]["id"]
        return TEAM_ID
    return None


def create_issue(title, description, team_id):
    """Create a new Linear Issue in Backlog."""
    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          url
          identifier
        }
      }
    }
    """
    variables = {
        "input": {
            "title": title,
            "description": description,
            "teamId": team_id
        }
    }
    
    result = graphql_query(mutation, variables)
    issue_data = result.get("data", {}).get("issueCreate", {})
    if issue_data.get("success"):
        return issue_data.get("issue", {})
    return None


def update_issue(issue_id, title, description):
    """Update an existing Linear Issue."""
    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) {
        success
        issue {
          id
          url
          identifier
        }
      }
    }
    """
    variables = {
        "id": issue_id,
        "input": {
            "title": title,
            "description": description
        }
    }
    
    result = graphql_query(mutation, variables)
    issue_data = result.get("data", {}).get("issueUpdate", {})
    return issue_data.get("success", False)


def extract_linear_issue_url(content):
    """Extract Linear Issue URL from markdown content."""
    # Look for either Doc or Issue tag to maintain backward compatibility during migration if needed, 
    # but primarily looking for Linear Issue.
    match = re.search(r'\*\*Linear Issue\*\*:\s*(https://linear\.app/[^\s\n]+)', content)
    if not match:
        match = re.search(r'\*\*Linear Doc\*\*:\s*(https://linear\.app/[^\s\n]+)', content)
    if match:
        return match.group(1).strip()
    return None


def extract_issue_identifier(url):
    """Extract issue identifier (e.g. PAC-123) from Linear URL."""
    # URL format: https://linear.app/workspace/issue/PAC-123/title
    match = re.search(r'/issue/([a-zA-Z0-9-]+)', url)
    if match:
        return match.group(1)
    return None


def extract_title(content):
    """Extract title from email note markdown."""
    match = re.search(r'^#\s+Email:\s*(.+)$', content, re.MULTILINE)
    if match:
        return f"[Email] {match.group(1).strip()}"
    return "[Email] Email Note"


def update_file_with_linear_url(filepath, linear_url, ident=None):
    """Update the markdown file with Linear Issue URL."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Update/Add Linear Issue line
    if "**Linear Issue**:" in content:
        # Replace empty Linear Issue line
        updated_content = re.sub(
            r'(\*\*Linear Issue\*\*:)\s*$',
            f'\\1 {linear_url}',
            content,
            flags=re.MULTILINE
        )
    elif "**Linear Doc**:" in content:
        # Convert Linear Doc to Linear Issue
        updated_content = re.sub(
            r'\*\*Linear Doc\*\*:\s*.*',
            f'**Linear Issue**: {linear_url}',
            content
        )
    else:
        # Add after the To: line or similar metadata
        updated_content = re.sub(
            r'(- \*\*To\*\*:[^\n]*\n)',
            f'\\1- **Linear Issue**: {linear_url}\n',
            content
        )
    
    # If no empty line found but we have the tag, try to add after tag
    if updated_content == content and "**Linear Issue**:" in content:
         updated_content = re.sub(
            r'(\*\*Linear Issue\*\*:)\s*\n',
            f'\\1 {linear_url}\n',
            content
        )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(updated_content)


def sync_email_notes():
    """Main sync function."""
    if not os.path.exists(EMAIL_NOTES_DIR):
        print(f"Error: {EMAIL_NOTES_DIR} directory not found")
        return
    
    # Get all markdown files except template
    md_files = glob.glob(os.path.join(EMAIL_NOTES_DIR, "*.md"))
    md_files = [f for f in md_files if not os.path.basename(f).startswith("_")]
    
    if not md_files:
        print(f"No email notes found in {EMAIL_NOTES_DIR}/")
        return
    
    print(f"Found {len(md_files)} email note(s) to sync...")
    
    # Get team ID
    team_id = get_team_id()
    if not team_id:
        print("Error: Could not find a team in Linear.")
        return
    
    for filepath in md_files:
        filename = os.path.basename(filepath)
        print(f"\nProcessing: {filename}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        title = extract_title(content)
        linear_url = extract_linear_issue_url(content)
        
        if linear_url:
            # Update existing issue
            ident = extract_issue_identifier(linear_url)
            if ident:
                print(f"  Updating existing issue: {ident}")
                # We need the UUID for update, or we can use identifier if we fetch it first.
                # Actually IssueUpdate requires the ID (UUID).
                
                # Let's fetch the UUID first
                query = f"""
                query {{
                  issue(id: "{ident}") {{
                    id
                  }}
                }}
                """
                res = graphql_query(query)
                issue_uuid = res.get("data", {}).get("issue", {}).get("id")
                
                if issue_uuid:
                    success = update_issue(issue_uuid, title, content)
                    if success:
                        print(f"  ✓ Updated successfully")
                        # Also ensure the file uses "Linear Issue" tag instead of "Linear Doc"
                        if "**Linear Doc**:" in content:
                           update_file_with_linear_url(filepath, linear_url)
                    else:
                        print(f"  ✗ Update failed")
                else:
                    print(f"  ✗ Could not find issue with identifier: {ident}")
            else:
                print(f"  ✗ Could not extract issue identifier from URL")
        else:
            # Create new issue
            print(f"  Creating new issue in Backlog...")
            issue = create_issue(title, content, team_id)
            if issue and issue.get("url"):
                new_url = issue["url"]
                new_ident = issue["identifier"]
                print(f"  ✓ Created: {new_ident} ({new_url})")
                
                # Update the markdown file with the Linear URL
                update_file_with_linear_url(filepath, new_url, new_ident)
                print(f"  ✓ Updated {filename} with Linear Issue link")
            else:
                print(f"  ✗ Failed to create issue")


if __name__ == "__main__":
    sync_email_notes()

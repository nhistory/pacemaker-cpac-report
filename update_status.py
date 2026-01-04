import os
import re
import requests
import json
import glob
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LINEAR_API_KEY")
URL = "https://api.linear.app/graphql"

if not API_KEY:
    print("Error: LINEAR_API_KEY not found in .env")
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

def get_issue_states(identifiers):
    """
    Fetches the state type for a list of issue identifiers (e.g., ['PAC-1', 'PAC-2']).
    Returns a dict: {'PAC-1': 'completed', 'PAC-2': 'started', ...}
    Using GraphQL aliases to batch fetch by identifier since 'issue(id: ...)' supports identifiers.
    """
    if not identifiers:
        return {}

    # Construct aliased query
    # {
    #   i0: issue(id: "PAC-1") { identifier state { type } }
    #   i1: issue(id: "PAC-2") { identifier state { type } }
    # }
    
    query_lines = ["query Issues {"]
    for idx, identifier in enumerate(identifiers):
        # escape identifier just in case, though usually safe
        safe_id = json.dumps(identifier) 
        query_lines.append(f'  i{idx}: issue(id: {safe_id}) {{ identifier state {{ type }} }}')
    query_lines.append("}")
    
    query = "\n".join(query_lines)
    
    result = graphql_query(query)
    
    states = {}
    if result.get("data"):
        for key, val in result["data"].items():
            if val and val.get("identifier") and val.get("state"):
                states[val["identifier"]] = val["state"]["type"]
            
    return states

def update_file(file_path):
    print(f"Checking {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Regex to find Linear Issue IDs in the link column or anywhere
    # Identifying pattern: [PAC-12](https://linear.app/...)
    # We specifically look for the table row structure to know which column to strike through.
    
    # Table structure expected: | Project | Priority | Item | ...
    
    ids_to_fetch = []
    line_map = [] # Store (line_index, identifier)
    
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
            
        # Check if line has linear link
        # Pattern: [PAC-XXXX](...
        match = re.search(r'\[([A-Z]+-\d+)\]\(https://linear\.app/', line)
        if match:
            identifier = match.group(1)
            ids_to_fetch.append(identifier)
            line_map.append((i, identifier))

    if not ids_to_fetch:
        # print("  No Linear links found.")
        return

    # Fetch statuses
    print(f"  Fetching status for {len(ids_to_fetch)} issues...")
    states = get_issue_states(ids_to_fetch)
    
    updates_made = 0
    
    for line_idx, identifier in line_map:
        state_type = states.get(identifier)
        if not state_type:
            continue
            
        # If Completed or Canceled, apply strikethrough to "Item" column (index 3)
        if state_type in ["completed", "canceled"]:
            line = lines[line_idx]
            parts = [p.strip() for p in line.split('|')]
            
            # Simple validation of table structure
            # | Project | Priority | Item | Description | ...
            # parts[0] is empty string (before first |), parts[1] is Project, parts[2] is Priority, parts[3] is Item
            if len(parts) >= 4:
                item_text = parts[3]
                
                # Check if already struck through
                if item_text.startswith("~~") and item_text.endswith("~~"):
                    continue
                
                # Apply strikethrough
                new_item_text = f"~~{item_text}~~"
                
                # Reconstruct line. Need to preserve original spacing? 
                # .split('|') destroys spacing. Better to just replace the text substring if possible, 
                # but valid markdown table doesn't require pretty alignment. 
                # To be safe and keep it clean, let's reconstruct simply.
                
                # Actually, simply replacing the string in the raw line might be safer to preserve other formatting
                # formatted_line = line.replace(f" {item_text} ", f" {new_item_text} ") 
                # but item_text from split calls .strip(), so we need to be careful.
                
                # Robust approach: Reconstruct the pipe-separated string.
                parts[3] = f" {new_item_text} " # Add padding spaces for readablity
                
                # Careful with empty first/last parts from split
                # if line started with |, parts[0] is ''
                # if line ended with |\n, parts[-1] is ''
                
                # Let's try to reconstruct strictly based on parts
                # We need to handle the padding of other cells to avoid ugly diffs?
                # For now, functional correctness > pretty alignment.
                
                # Retain original padding for other cells? Too hard.
                # Just join with " | "
                
                # Wait, let's try to just replace the specific "Item" text if it's unique enough?
                # No, "Meeting" might appear multiple times.
                
                # Let's go with reconstruction.
                # We stripped parts earlier for logic.
                # Let's re-split WITHOUT stripping to preserve whitespace?
                raw_parts = line.split('|')
                # raw_parts[3] is the one we want to change.
                
                # we know raw_parts[3].strip() == item_text
                # we want to replace item_text with ~~item_text~~ within raw_parts[3]
                
                original_cell_content = raw_parts[3]
                new_cell_content = original_cell_content.replace(item_text, new_item_text, 1)
                
                raw_parts[3] = new_cell_content
                new_line = "|".join(raw_parts)
                
                lines[line_idx] = new_line
                updates_made += 1
                print(f"  -> Marked {identifier} as {state_type}: {item_text}")

    if updates_made > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"  Saved {updates_made} updates to {file_path}")
    else:
        print("  No updates needed.")

if __name__ == "__main__":
    # Scan all markdown files in meeting_notes/
    target_dir = "meeting_notes" 
    files = glob.glob(os.path.join(target_dir, "*.md"))
    
    print(f"Target Directory: {target_dir}")
    print(f"Found {len(files)} markdown files.")
    
    for file_path in files:
        update_file(file_path)

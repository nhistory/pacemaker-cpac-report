import os
import requests
import json
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

query = """
query {
  teams {
    nodes {
      id
      name
      key
    }
  }
  workflowStates {
    nodes {
        id
        name
        type
        team {
            id
        }
    }
  }
}
"""

response = requests.post(URL, headers=headers, json={"query": query})

if response.status_code == 200:
    data = response.json()
    print("\n--- Teams ---")
    for team in data.get("data", {}).get("teams", {}).get("nodes", []):
        print(f"Name: {team['name']}, Key: {team['key']}, ID: {team['id']}")
    
    print("\n--- Workflow States ---")
    for state in data.get("data", {}).get("workflowStates", {}).get("nodes", []):
        print(f"Name: {state['name']}, Type: {state['type']}, ID: {state['id']}")
else:
    print(f"Error: {response.status_code}, {response.text}")

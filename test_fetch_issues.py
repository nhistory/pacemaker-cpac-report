import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LINEAR_API_KEY")
URL = "https://api.linear.app/graphql"

headers = {
    "Authorization": API_KEY,
    "Content-Type": "application/json"
}

query = """
query {
  issues(first: 50, filter: { state: { name: { neq: "Done" } } }) {
    nodes {
      id
      identifier
      title
      state {
        name
      }
      assignee {
        name
      }
    }
  }
}
"""

response = requests.post(URL, headers=headers, json={"query": query})

if response.status_code == 200:
    data = response.json()
    issues = data.get("data", {}).get("issues", {}).get("nodes", [])
    print(f"Found {len(issues)} issues:")
    for issue in issues:
        assignee = issue['assignee']['name'] if issue['assignee'] else "Unassigned"
        print(f"- [{issue['identifier']}] {issue['title']} ({issue['state']['name']}) - {assignee}")
else:
    print(f"Error: {response.status_code}, {response.text}")

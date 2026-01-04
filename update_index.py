import os
import json
from bs4 import BeautifulSoup

def index_reports():
    base_dir = "/Users/sehwanlee/Documents/Coding/04 Pacemaker/non-profit/html"
    index_file = os.path.join(base_dir, "search-index.json")
    reports = []

    # Directories to exclude or search in
    # For now, let's look at all directories that look like dates or have an index.html
    for root, dirs, files in os.walk(base_dir):
        if "index.html" in files:
            # Skip the root index.html
            if root == base_dir:
                continue
            
            rel_path = os.path.relpath(root, base_dir)
            html_path = os.path.join(root, "index.html")
            
            with open(html_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                
                # Extract data
                title = soup.title.string.replace(" | Pacemaker", "") if soup.title else rel_path
                date_elem = soup.find(class_="report-date")
                date = date_elem.get_text() if date_elem else ""
                
                # Extract all text content
                # We specifically want text from 'main' or 'container'
                main_content = soup.find("main")
                if main_content:
                    # Clean up the text
                    text = main_content.get_text(separator=" ", strip=True)
                else:
                    text = soup.get_text(separator=" ", strip=True)

                # Extract tags if any
                tags = [tag.get_text() for tag in soup.find_all(class_="tag")]
                
                reports.append({
                    "id": rel_path,
                    "title": title,
                    "date": date,
                    "tags": tags,
                    "content": text,
                    "url": f"./{rel_path}/"
                })

    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    
    print(f"Successfully indexed {len(reports)} reports to {index_file}")

if __name__ == "__main__":
    index_reports()

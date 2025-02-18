import os
import json
from langchain.schema import Document


def ingest_json(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        docs = []
        for entry in data:
            text = f"Title: {entry.get('title', 'Unknown')}\n" \
                   f"URL: {entry.get('url', 'No URL')}\n" \
                   f"Category: {entry.get('category', 'Uncategorized')}\n" \
                   f"Description: {entry.get('description', 'No description')}"

            docs.append(Document(page_content=text))

        print(f"Loaded {len(docs)} entries from {file_path}")
        return docs

    except json.JSONDecodeError as e:
        print(f"JSON Parsing Error in {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error loading JSON {file_path}: {e}")
        return []

# def ingest_json(data_dir="data"):
#     pwd = os.getcwd()
#     data_path = os.path.join(pwd, data_dir)
#     print(f"Looking for JSON files in {data_path}")

#     all_docs = []
#     for root, _, files in os.walk(data_path):
#         for file in files:
#             if file.endswith(".json"):
#                 file_path = os.path.join(root, file)
#                 print(f"Loading JSON from {file_path}")
#                 all_docs.extend(load_json(file_path))

#     if not all_docs:
#         print("No valid JSON documents found.")
#         return []
    
#     return all_docs
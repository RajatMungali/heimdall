import json

with open("backend/test_scrapecreators_threads_us_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

for k, v in data.items():
    print(f"Keyword: '{k}' -> Total Items: {v.get('total_items')}")

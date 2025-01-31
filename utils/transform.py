import json

with open('./companies.json', 'r') as f:
  data = json.load(f)
  
for i, attr in enumerate(data):
  data[attr]['sub_sector'] = data[attr]['sub_sector'].replace('&', '').replace(',', '').replace('  ', ' ').replace(' ', '-').lower()
  
with open('./companies.json', 'w') as f:
  json.dump(data, f, indent=2)
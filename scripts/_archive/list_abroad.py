import json
d = json.load(open('data/crawled/city_index.json', encoding='utf-8'))
cities = [c for c in d['all_cities'] if c['region'] == 'abroad']
print(f'国外共 {len(cities)} 个')
for c in cities:
    print(f"{c['id']:6d}  {c['name']}")

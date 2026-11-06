import os
import re
import csv
from dotenv import load_dotenv

load_dotenv()

TABLE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'assets_table.txt')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'data', 'assets.csv')

def parse_rows(text):
    rows = []
    for line in text.splitlines():
        m = re.match(r'^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|$', line)
        if not m:
            continue
        idx, code, name, category, location = m.groups()
        if code == 'كود الأصل':
            continue
        rows.append({
            'asset_code': code.strip(),
            'asset_name': name.strip(),
            'category': category.strip() or 'آلات ومعدات',
            'location': location.strip() or 'نوربيcko',
            'status': 'يعمل بحالة جيدة',
        })
    return rows

def load_rows():
    with open(TABLE_PATH, encoding='utf-8') as f:
        return parse_rows(f.read())

def export_csv(rows, path=CSV_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=['asset_code','asset_name','category','location','status'])
        w.writeheader()
        w.writerows(rows)
    print(f'Exported {len(rows)} rows to {path}')

def seed(db, Asset):
    rows = load_rows()
    added = 0
    for r in rows:
        if not Asset.query.filter_by(asset_code=r['asset_code']).first():
            db.session.add(Asset(**r))
            added += 1
    db.session.commit()
    print(f'Seeded {added} new assets (total parsed: {len(rows)})')

if __name__ == '__main__':
    rows = load_rows()
    export_csv(rows)
    print(f'Parsed {len(rows)} assets')

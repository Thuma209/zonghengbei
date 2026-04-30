import sqlite3, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'game.db'))
conn.row_factory = sqlite3.Row

print('=== 国家数据 (AAA/ZZZ) ===')
for row in conn.execute("SELECT code,year,war_status,civ_ic,mil_ic,nav_ic,policies,techs,stability,war_support,stockpile,facilities FROM nation WHERE code='AAA' OR code='ZZZ'"):
    d = dict(row)
    print(f"\n{d['code']}: year={d['year']}, war={d['war_status']}, stab={d['stability']}, ws={d['war_support']}")
    print(f"  civ_ic={d['civ_ic']}, mil_ic={d['mil_ic']}, nav_ic={d['nav_ic']}")
    print(f"  policies={d['policies']}")
    print(f"  techs={d['techs']}")
    print(f"  stockpile={d['stockpile']}")
    print(f"  facilities={d['facilities']}")

print('\n=== 地块数据 (A514/A810) ===')
for row in conn.execute("SELECT code,name,is_coastal,occupation_type,factories,resources FROM tile WHERE code='A514' OR code='A810'"):
    d = dict(row)
    print(f"\n{d['code']} ({d['name']}): coastal={d['is_coastal']}, type={d['occupation_type']}")
    print(f"  factories={d['factories']}")
    print(f"  resources={d['resources']}")

conn.close()

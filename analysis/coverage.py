"""Which detailed suppliers of the data package appear in a practice case, and what the others look like."""

import collections
import re
import sqlite3

from _common import PACKAGE, load_cases, short

db = sqlite3.connect(f"file:{PACKAGE / 'world.sqlite'}?mode=ro", uri=True)
db.row_factory = sqlite3.Row
in_case = collections.defaultdict(list)
for c in load_cases("practice"):
    for s in c["suppliers"]:
        in_case[s].append(short(c))
full = [r["id"] for r in db.execute("select id from suppliers where detail='full' order by id")]
unseen = [s for s in full if s not in in_case]
print(f"detailed suppliers: {len(full)} | in a practice case: {len(in_case)} | in none: {len(unseen)}")
print("in none:", ", ".join(s.split(":")[1] for s in unseen))


def n(table, s):
    return db.execute(f"select count(*) from {table} where supplier_id=?", (s,)).fetchone()[0]


print("\nid     category        owner    case      docs news quotes ctr_to      name")
for s in full:
    r = db.execute(
        "select s.name, s.category, i.owner_type from suppliers s "
        "left join supplier_intel i on i.supplier_id=s.id where s.id=?",
        (s,),
    ).fetchone()
    to = db.execute("select valid_to from contracts where supplier_id=?", (s,)).fetchone()
    print(
        f"{s.split(':')[1]:6} {r['category'][:15]:15} {str(r['owner_type'])[:8]:8} {','.join(in_case.get(s, ['-'])):9} "
        f"{n('documents', s):4} {n('news', s):4} {n('quotes', s):6} {to[0] if to else '-':11} {r['name'][:40]}"
    )


def ids(query):
    return [r for r in db.execute(query) if r["supplier_id"] in unseen]


suffixes = collections.Counter(
    re.sub(r"\d+", "#", r["id"].rsplit("-", 1)[-1]) for r in db.execute("select id from documents")
)
print("\ndocument ID suffixes:", suffixes.most_common())
print("\ncandidate triggers among suppliers in no practice case")
ending = ids("select supplier_id from contracts where valid_to='2026-12-31'")
print("  contracts ending 2026-12-31:", [r["supplier_id"].split(":")[1] for r in ending])
red = ids("select supplier_id from scorecards where quarter='2026Q3' and colour='red'")
print("  red scorecards 2026Q3:", [r["supplier_id"].split(":")[1] for r in red])
bench = ids("select q.supplier_id, q.part_id from quotes q join rfqs r on r.id=q.rfq_id where r.status='quoted'")
print("  quoted second-source benchmarks:", [(r["supplier_id"].split(":")[1], r["part_id"]) for r in bench])

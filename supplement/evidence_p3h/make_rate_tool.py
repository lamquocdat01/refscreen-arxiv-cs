# Builds P3H/rate_tool.html: a self-contained page for the author's confirmation pass (Amendment 9 (E)).
# Reads only the blind sheet, the machine check and the empty form. Does not read any key.
import csv, json, io
def rd(p): return list(csv.DictReader(open(p, encoding='utf-8-sig')))
sheet = {r['ID']: r for r in rd('results/p3h_evidence_sheet.csv')}
chk = {r['ID']: r for r in rd('results/p3h_evidence_checked.csv')}
ids = [r['ID'] for r in rd('results/p3h_evidence_author_form.csv')]
rows = []
for i in ids:
    s, c = sheet[i], chk[i]
    rows.append({'id': i, 'ref': s['reference'], 'title': s['title'], 'authors': s['authors'],
                 'year': s['year'], 'venue': s['venue'], 'url': c['url'], 'state': c['state'],
                 'page_title': c['page_title'], 'sim': c['sim'], 'surn': c['surnames_matched'],
                 'page_year': c['page_year']})
html = open('P3H/rate_tool_template.html', encoding='utf-8').read().replace('/*DATA*/[]', json.dumps(rows, ensure_ascii=False))
open('P3H/rate_tool.html', 'w', encoding='utf-8', newline='\n').write(html)
print(len(rows), 'rows ->', 'P3H/rate_tool.html')

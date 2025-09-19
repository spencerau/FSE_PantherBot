import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / 'data' / 'major_catalog_json'

PASS_PATTERNS = [
    r'Letter grade with Pass/No Pass option\.?',
    r'Letter grade with P/NP option\.?',
    r'Letter grade with P/NP\.?',
    r'Letter grade with Pass/No Pass\.?',
    r'Pass/No Pass option\.?',
    r'Pass/No Pass\.?',
    r'P/NP\.?',
    r'P/NP option\.?'
]
PASS_RE = re.compile('|'.join(PASS_PATTERNS), flags=re.IGNORECASE)

EXEMPT_RE = re.compile(r'.*(298|398)$')

changed_files = []

for year_dir in BASE.iterdir():
    if not year_dir.is_dir():
        continue
    for jf in year_dir.glob('*.json'):
        data = json.loads(jf.read_text(encoding='utf-8'))
        modified = False
        # backup
        backup = jf.with_suffix(jf.suffix + '.bak')
        if not backup.exists():
            backup.write_text(jf.read_text(encoding='utf-8'), encoding='utf-8')
        # traverse sections -> courses
        sections = data.get('sections', [])
        for sec in sections:
            courses = sec.get('courses', [])
            for course in courses:
                cnum = course.get('course_number', '').strip()
                if not cnum:
                    continue
                # Exempt ENGR 101 and any 298/398
                if cnum.upper() == 'ENGR 101' or EXEMPT_RE.match(cnum):
                    continue
                desc = course.get('description', '')
                if not desc:
                    continue
                new_desc = PASS_RE.sub('', desc)
                # normalize repeated spaces
                new_desc = re.sub(r'\s{2,}', ' ', new_desc).strip()
                # ensure there is a sentence marker before parenthesis groups
                # If 'Letter grade' not mentioned, append it before final parenthetical or at end
                if 'letter grade' not in new_desc.lower():
                    # find last ' (' occurrence indicating the start of parenthetical like (Offered...)
                    idx = new_desc.rfind(' (')
                    if idx != -1:
                        new_desc = new_desc[:idx].rstrip() + ' Letter grade.' + ' ' + new_desc[idx+1:]
                    else:
                        new_desc = new_desc.rstrip('.') + '. Letter grade.'
                # clean up duplicate periods
                new_desc = re.sub(r'\.\s*\.', '.', new_desc)
                if new_desc != desc:
                    course['description'] = new_desc
                    modified = True
        if modified:
            jf.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
            changed_files.append(str(jf))

print('Modified files:')
for f in changed_files:
    print(f)
print('Done.')

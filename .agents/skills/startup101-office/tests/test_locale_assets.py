# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Complete locale coverage and source-reference checks. Run after translation assembly."""
import json
from pathlib import Path
import re
SKILL=Path(__file__).resolve().parents[1]
original=json.loads((SKILL/'assets/catalog.json').read_text())
zh=json.loads((SKILL/'assets/locales/zh-TW.json').read_text())
en=json.loads((SKILL/'assets/locales/en.json').read_text())
ids={q['id'] for q in original['questions']}
assert set(zh['questions'])==ids
assert len(ids)==362
assert all(c['name'] in zh['categories'] for c in original['categories'])
for q in original['questions']:
 translated=zh['questions'][q['id']]
 assert re.search('[\u3400-\u9fff]',translated['question']),q['id']
 assert translated['question']!=q['question']
 for key in ('why','example','avoid'):
  assert translated['help'][key].strip(),(q['id'],key)
  assert re.search('[\u3400-\u9fff]',translated['help'][key]),(q['id'],key)
 assert translated['help']['synthetic'] is True
 assert en['questions'][q['id']].get('question',q['question'])==q['question']
 assert en['questions'][q['id']]['help']==q['help'],(q['id'],'English help changed')
 assert 'grounding' not in translated
print('PASS: complete bilingual coverage, stable questions, synthetic labels, no course quotations')

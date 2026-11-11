# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Language inference uses local prose, never generated catalogs or code."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('setup',Path(__file__).resolve().parents[1]/'scripts/setup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LanguageTests(unittest.TestCase):
 def test_chinese_and_exclusions(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'README.md').write_text('這是團隊的產品規劃與顧客訪談資料。'*30)
   for name in ['node_modules','view','.startup101','runtime']:
    (p/name).mkdir();(p/name/'catalog.md').write_text('English generated startup project catalog sample. '*500)
   (p/'nested').mkdir();(p/'nested/.git').write_text('gitdir: elsewhere');(p/'nested/README.md').write_text('English ignored nested repository. '*500)
   (p/'source.md').write_text('```javascript\n'+('const english = "ignore generated code";\n'*500)+'```')
   d=m.detect_locale(p);self.assertEqual(d['locale'],'zh-TW');self.assertEqual(d['english_words'],0);self.assertEqual(d['sampled_files'],1)
 def test_english_empty_and_answers(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);self.assertEqual(m.detect_locale(p)['reason'],'ambiguous-default-en')
   (p/'README.md').write_text('Customers need specific evidence before choosing the product. '*50)
   self.assertEqual(m.detect_locale(p)['locale'],'en')
   (p/'README.md').unlink()
   (p/'startup101.md').write_text('# English generated heading\n```startup101-project\n{"title":"English generated"}\n```\n## More generated question headings\n```startup101-text\n'+('我們訪談的顧客每週都需要重新整理訂單。'*30)+'\n```\n')
   d=m.detect_locale(p);self.assertEqual(d['locale'],'zh-TW');self.assertEqual(d['english_words'],0)
 def test_generated_readme(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);(p/'README.md').write_text('<!-- startup101-generated-readme -->'+('生成的中文文件。'*100))
   self.assertEqual(m.detect_locale(p)['reason'],'ambiguous-default-en')
 def test_bound(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)
   for n in range(10):(p/f'{n}.md').write_text('A meaningful English project document for local startup planning. '*20)
   self.assertEqual(m.detect_locale(p,max_files=2)['sampled_files'],2)
if __name__=='__main__':unittest.main()

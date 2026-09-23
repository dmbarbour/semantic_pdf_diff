import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import fitz
from semantic_pdf_diff.models import Evidence, Settings, Extraction, Judgment
from semantic_pdf_diff.llm import Client, BudgetExceeded, ModelFailure
from semantic_pdf_diff.compare import candidates, numeric_check, compare
from semantic_pdf_diff.extract import extract_pdf, split_utf8, tiles
from semantic_pdf_diff.report import write_report


def ev(id='A-1', **kw):
    data = dict(id=id, document=id[0],page=1,bbox=(0,0,100,100),source='text:0',entity='primary pump',
        attribute='rated power',value='10',unit='kW',conditions='design load',kind='text',quote='10 kW',confidence=.95)
    data.update(kw)
    return Evidence(**data)

class Fake:
    def __init__(self,s=None,relation='different',same=True):
        self.s = s or Settings()
        self.relation,self.same = relation,same
    def ask(self,prompt,schema,images=()):
        if schema is Judgment:
            return Judgment(relation=self.relation,rationale='Fixture judgment',confidence=.95,same_conditions=self.same)
        raise AssertionError('Unexpected extraction')

class Tests(unittest.TestCase):
    def test_units_and_nonliteral(self):
        self.assertTrue(numeric_check(ev(),ev('B-1',value='10000',unit='W'))['equal'])
        self.assertIsNone(numeric_check(ev(value='>=10'),ev('B-1')))
        self.assertIsNone(numeric_check(ev(approximate=True),ev('B-1')))
        self.assertIsNone(numeric_check(ev(unit='ton'),ev('B-1')))
        self.assertIsNone(numeric_check(ev(),ev('B-1',unit='kPa')))

    def test_cross_format_and_one_to_many(self):
        a = [ev()]
        b = [ev('B-1',kind='table',value='12'),ev('B-2',kind='chart',value='11')]
        self.assertEqual(len(candidates(a,b,Settings(top_k=1))),2)
        result = compare(a,b,Path('.'),Fake(),'proposals')
        self.assertEqual({f['relation'] for f in result['findings']},{'different'})

    def test_condition_and_numeric_veto(self):
        with tempfile.TemporaryDirectory() as d:
            for client in [Fake(same=False),Fake(relation='equivalent')]:
                result = compare([ev()],[ev('B-1',value='12')],Path(d),client,'revisions')
                self.assertEqual(result['findings'][0]['relation'],'uncertain')
                self.assertEqual(len(result['unmatched']),2)

    def test_utf8_and_tiles(self):
        text = '冷却水 pump '*300
        chunks = list(split_utf8(text,200))
        self.assertEqual(''.join(chunks),text)
        self.assertTrue(all(len(x.encode())<=200 for x in chunks))
        rect = fitz.Rect(0,0,600,900)
        regions = list(tiles(rect,420))
        for y in range(0,900,10):
            for x in range(0,600,10):
                self.assertTrue(any(r.contains(fitz.Point(x,y)) for r in regions))

    def test_api_retry_cache_truncation_and_budget(self):
        state = {'calls':0,'truncate':False}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                self.server.payload = body
                state['calls'] += 1
                answer = 'bad json' if state['calls']==1 else '{"claims":[],"complete":true,"issues":[]}'
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'choices':[{'finish_reason':'length' if state['truncate'] else 'stop',
                    'message':{'content':answer}}]}).encode())
        server = HTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                s = Settings(base_url=f'http://127.0.0.1:{server.server_port}/v1',retries=1,max_calls=4)
                c = Client(s,Path(d))
                self.assertTrue(c.ask('extract',Extraction).complete)
                c.ask('extract',Extraction)
                self.assertEqual(state['calls'],2)
                self.assertEqual(c.cache_hits,1)
                with self.assertRaises(BudgetExceeded): c.ask('x'*10000,Extraction)
                state['truncate']=True
                with self.assertRaises(ModelFailure): c.ask('another request',Extraction)
                with self.assertRaises(BudgetExceeded): c.ask('limit',Extraction)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_extraction_coverage_and_unsupported_quote(self):
        class Extractor(Fake):
            def ask(self,prompt,schema,images=()):
                from semantic_pdf_diff.models import Claim
                data=ev().model_dump(include=set(Claim.model_fields))
                data['quote']='invented support'
                return Extraction(claims=[data],complete=True)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.pdf'
            doc=fitz.open();page=doc.new_page();page.insert_text((40,40),'Pump rated power 10 kW');doc.save(path);doc.close()
            evidence,coverage,digest=extract_pdf(path,'A',Path(d),Extractor(Settings(vision=False)))
            self.assertEqual(evidence,[])
            self.assertTrue(any(r['status']=='partial' for r in coverage))
            self.assertTrue(any(r['status']=='skipped' for r in coverage))

    def test_cli_end_to_end_with_images_and_cache(self):
        from semantic_pdf_diff.cli import main
        from semantic_pdf_diff.models import Claim
        state = {'images':0,'calls':0}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state['calls'] += 1
                parts=data['messages'][1]['content']
                for part in parts:
                    if part['type']=='image_url':
                        state['images'] += 1
                        assert part['image_url']['url'].startswith('data:image/png;base64,')
                prompt=parts[0]['text']
                if 'Compare exactly' in prompt:
                    answer=Judgment(relation='equivalent',rationale='Controlled same-value fixture',confidence=.95,same_conditions=True).model_dump()
                else:
                    claim=ev().model_dump(include=set(Claim.model_fields))
                    claim['quote']='10 kW'
                    answer={'claims':[claim],'complete':True,'issues':[]}
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(answer)}}]}).encode())
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                for name in ['a','b']:
                    doc=fitz.open();page=doc.new_page(width=300,height=300)
                    page.insert_text((40,40),'Pump rated power 10 kW at design load')
                    page.draw_rect(fitz.Rect(40,80,120,120))
                    page.draw_line(fitz.Point(120,100),fitz.Point(220,100))
                    doc.save(root/(name+'.pdf'));doc.close()
                config=root/'config.json'
                config.write_text(json.dumps({'base_url':f'http://127.0.0.1:{server.server_port}/v1','retries':0}))
                args=[str(root/'a.pdf'),str(root/'b.pdf'),'--out',str(root/'out'),'--config',str(config)]
                self.assertEqual(main(args),0)
                result=json.loads((root/'out/report.json').read_text())
                self.assertGreater(state['images'],0)
                self.assertGreater(len(result['findings']),0)
                self.assertTrue(list((root/'out/assets').glob('*.png')))
                before=state['calls']
                self.assertEqual(main(args),0)
                self.assertEqual(state['calls'],before)
        finally:
            server.shutdown();server.server_close();thread.join()

    def test_refinement_preserves_failure_ledger(self):
        from semantic_pdf_diff.models import Claim
        class Extractor(Fake):
            count=0
            def ask(self,prompt,schema,images=()):
                self.count+=1
                return Extraction(claims=[],complete=False,issues=['Dense visual'])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'test.pdf'
            doc=fitz.open();doc.new_page(width=500,height=500);doc.save(path);doc.close()
            client=Extractor(Settings(refinement_depth=1))
            _,coverage,_=extract_pdf(path,'A',root,client)
            self.assertTrue(any('-r' in r['source'] for r in coverage))
            self.assertTrue(all(r['status']=='partial' for r in coverage))

    def test_html_escapes_document_content(self):
        a,b=ev(entity='<script>alert(1)</script>'),ev('B-1')
        data=compare([a],[b],Path('.'),Fake(),'proposals')
        data.update(evidence=[a.model_dump(),b.model_dump()],coverage=[],documents={'A':{'name':'A.pdf'},'B':{'name':'B.pdf'}})
        with tempfile.TemporaryDirectory() as d:
            write_report(data,Path(d))
            html=(Path(d)/'report.html').read_text()
            self.assertNotIn('<script>alert(1)</script>',html)
            self.assertIn('&lt;script&gt;',html)

if __name__=='__main__': unittest.main()

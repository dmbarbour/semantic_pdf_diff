"""Generate a transparent, hand-authored evidence fixture report without API access.
This demonstrates matching/reporting, not VLM extraction accuracy.
Run from repository root: python examples/demo.py
"""
from pathlib import Path
from semantic_pdf_diff.models import Evidence, FileRef, PdfLocator, Settings, Source, Judgment
from semantic_pdf_diff.compare import compare
from semantic_pdf_diff.report import write_report


# Placeholder content IDs: this fixture has no real files behind it.
CONTENT={'A':'sha256:'+'a'*64+'.pdf','B':'sha256:'+'b'*64+'.pdf'}

def claim(id,entity,attribute,value,unit,kind,conditions='design duty',**extra):
    return Evidence(id=id,content=CONTENT[id[0]],locator=PdfLocator(page=1,bbox=(40,40,300,140),region='text',task='hand-authored fixture'),
        entity=entity,attribute=attribute,value=value,unit=unit,kind=kind,conditions=conditions,
        quote=f'{entity}: {attribute} {value} {unit} at {conditions}',confidence=.95,**extra)

left=[claim('A-1','primary pump','rated power','10','kW','text'),
      claim('A-2','cooling circuit','design flow','20','L/s','table'),
      claim('A-3','primary pump','discharges to','heat exchanger','','diagram'),
      claim('A-4','pump','head at 20 L/s','35','m','chart',approximate=True)]
right=[claim('B-1','primary pump','rated power','12000','W','table'),
       claim('B-2','cooling circuit','design flow','0.020','m3/s','text'),
       claim('B-3','primary pump','discharges to','heat exchanger','','text'),
       claim('B-4','pump','head at 20 L/s','32','m','chart',approximate=True),
       claim('B-5','firewall','audit log retention','90','days','text',conditions='security policy')]

class FixtureClient:
    s=Settings(top_k=1,min_score=.25)
    def ask(self,prompt,schema,images=(),key=None):
        import json
        a=json.loads(prompt.split('\nA=')[1].split('\nB=')[0])
        b=json.loads(prompt.split('\nB=')[1].split('\nNumeric check=')[0])
        relation='unrelated';reason='Distinct properties in the hand-authored fixture.'
        if a['attribute']==b['attribute']:
            relation='equivalent' if a['attribute'] in ('design flow','discharges to') else 'different'
            reason={'rated power':'At design duty, rated power increases from 10 kW to 12 kW (+20%).',
                    'design flow':'The table value 20 L/s equals the prose value 0.020 m3/s.',
                    'discharges to':'The diagram connection and prose specify the same discharge destination.',
                    'head at 20 L/s':'Chart readings suggest 35 m versus 32 m; both are approximate.'}[a['attribute']]
        return Judgment(relation=relation,rationale=reason,confidence=.95,same_conditions=True)

out=Path('examples/demo-output')
data=compare(left,right,out,FixtureClient(),'proposals')
data.update(schema_version=2,fixture=True,
    sources=[Source(id='s1',name='Team A (synthetic evidence)',kind='file').model_dump(),
             Source(id='s2',name='Team B (synthetic evidence)',kind='file').model_dump()],
    files=[FileRef(source='s1',path='team-a.pdf',content=CONTENT['A']).model_dump(),
           FileRef(source='s2',path='team-b.pdf',content=CONTENT['B']).model_dump()],
    evidence=[e.model_dump() for e in left+right],coverage=[],
    note='HAND-AUTHORED FIXTURE: no PDF extraction or real model inference was used. This report demonstrates behavior, not measured accuracy.')
write_report(data,out)
print(out/'report.html')

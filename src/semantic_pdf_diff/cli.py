import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from .models import Settings
from .llm import Client, redact_url
from .extract import extract_pdf, visual_regions
from .compare import compare
from .report import write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidence-first PDF comparison using a small OpenAI-compatible VLM")
    parser.add_argument('a', type=Path, help='Proposal A / earlier revision')
    parser.add_argument('b', type=Path, help='Proposal B / later revision')
    parser.add_argument('--out', type=Path, default=Path('diff-output'))
    parser.add_argument('--config', type=Path, help='Settings JSON; overrides environment defaults, CLI flags override it')
    parser.add_argument('--mode', choices=['proposals','revisions'], default='proposals')
    parser.add_argument('--model')
    parser.add_argument('--base-url')
    parser.add_argument('--context-tokens', type=int)
    parser.add_argument('--max-calls', type=int)
    parser.add_argument('--top-k', type=int)
    parser.add_argument('--no-vision', action='store_true', help='Explicitly incomplete text-only run')
    parser.add_argument('--plan', action='store_true', help='Inspect pages and estimate visual tasks without API calls')
    args = parser.parse_args(argv)
    try:
        options = json.loads(args.config.read_text()) if args.config else {}
        if not isinstance(options, dict):
            raise ValueError(f'{args.config}: settings file must contain a JSON object')
        for name in ['model','base_url','context_tokens','max_calls','top_k']:
            if getattr(args,name) is not None:
                options[name] = getattr(args,name)
        if args.no_vision:
            options['vision'] = False
        settings = Settings.from_env(**options)
        if args.plan:
            import pymupdf
            result = {}
            for label,path in [('A',args.a),('B',args.b)]:
                with pymupdf.open(path) as doc:
                    visual = sum(len(visual_regions(p, settings.tile_points)) for p in doc) if settings.vision else 0
                    result[label] = {'pages':len(doc),'visual_tasks':visual}
            print(json.dumps({'documents':result, 'max_calls':settings.max_calls,
                'note':'Native text/table extraction, pair comparisons, retries and adaptive refinement add calls; no API requests made.'},indent=2))
            return 0
        args.out.mkdir(parents=True,exist_ok=True)
        client = Client(settings,args.out/'cache')
        claims, coverage, documents = {}, [], {}
        for label,path in [('A',args.a),('B',args.b)]:
            print(f'Extracting {label}: {path.name}',file=sys.stderr)
            claims[label], ledger, digest = extract_pdf(path,label,args.out,client)
            coverage.extend(ledger)
            documents[label] = {'name':path.name,'sha256':digest}
            (args.out/f'evidence-{label}.json').write_text(json.dumps({'document':documents[label],
                'evidence':[e.model_dump() for e in claims[label]],'coverage':ledger},indent=2),encoding='utf-8')
        print(f"Comparing {len(claims['A'])} × {len(claims['B'])} extracted claims via retrieval",file=sys.stderr)
        data = compare(claims['A'],claims['B'],args.out,client,args.mode)
        data.update(schema_version=1, created_at=datetime.now(timezone.utc).isoformat(),documents=documents,
            evidence=[e.model_dump() for e in claims['A']+claims['B']],coverage=coverage,
            settings={**settings.model_dump(), 'base_url':redact_url(settings.base_url)}, usage={'api_calls':client.calls,'cache_hits':client.cache_hits,**client.usage},
            limitations=['Image-token budgeting must be calibrated to the serving backend.',
                'Confidence scores are uncalibrated model self-reports.',
                'Retrieval may miss synonyms and implicit relationships; configure domain aliases.',
                'Small VLMs can misread plots, tables, scales and diagram arrows.',
                'No global engineering consistency proof or automatic proposal ranking.'])
        write_report(data,args.out)
        incomplete = any(r['status']!='complete' for r in coverage) or not claims['A'] or not claims['B'] or data['retrieval']['omitted_by_pair_limit']>0 or any(f.get('processing_error') for f in data['findings'])
        print(f"Report: {args.out/'report.html'}" + (' (incomplete source coverage)' if incomplete else ''))
        # 2 makes automation aware of incomplete processing; uncertainty still appears
        # in the report even when all tasks completed successfully.
        return 2 if incomplete else 0
    except (OSError, ValueError, RuntimeError) as e:
        print(f'Error: {e}',file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())

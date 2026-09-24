import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from .models import FileRef, Settings, Source
from .llm import Client, redact_url
from .provenance import comparison_interpreter, content_id, extraction_interpreter
from .extract import extract_pdf, visual_regions
from .compare import compare
from .report import write_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evidence-first PDF comparison using a small OpenAI-compatible VLM")
    parser.add_argument('a', type=Path, help='First source (a PDF): proposal A, or the earlier revision')
    parser.add_argument('b', type=Path, help='Second source (a PDF): proposal B, or the later revision')
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
        paths = [args.a, args.b]
        sources, files = register_sources(paths)
        if args.plan:
            import pymupdf
            result = []
            for source, path in zip(sources, paths):
                with pymupdf.open(path) as doc:
                    visual = sum(len(visual_regions(p, settings.tile_points)) for p in doc) if settings.vision else 0
                    result.append({'source':source.id, 'name':source.name, 'pages':len(doc), 'visual_tasks':visual})
            print(json.dumps({'sources':result, 'max_calls':settings.max_calls,
                'note':'Native text/table extraction, pair comparisons, retries and adaptive refinement add calls; no API requests made.'},indent=2))
            return 0
        args.out.mkdir(parents=True,exist_ok=True)
        client = Client(settings,args.out/'cache')
        by_content, coverage = {}, []
        for file, path in zip(files, paths):
            if file.content in by_content:
                print(f'Already extracted: {file.path} (same content)',file=sys.stderr)
                continue
            print(f'Extracting {file.path}',file=sys.stderr)
            by_content[file.content], ledger = extract_pdf(path,file.content,args.out,client)
            coverage.extend(ledger)
        evidence = [e for items in by_content.values() for e in items]
        interpreters = {'extract':extraction_interpreter(settings).model_dump()}
        (args.out/'evidence.json').write_text(json.dumps({'schema_version':2,'sources':[x.model_dump() for x in sources],
            'files':[f.model_dump() for f in files],'interpreters':interpreters,'evidence':[e.model_dump() for e in evidence],
            'coverage':coverage},indent=2,ensure_ascii=False),encoding='utf-8')
        left, right = (by_content[f.content] for f in files)
        print(f"Comparing {len(left)} × {len(right)} extracted claims via retrieval",file=sys.stderr)
        data = compare(left,right,args.out,client,args.mode)
        interpreters['compare'] = comparison_interpreter(settings).model_dump()
        data.update(schema_version=2, created_at=datetime.now(timezone.utc).isoformat(),
            sources=[x.model_dump() for x in sources], files=[f.model_dump() for f in files], interpreters=interpreters,
            evidence=[e.model_dump() for e in evidence],coverage=coverage,
            settings={**settings.model_dump(), 'base_url':redact_url(settings.base_url)}, usage={'api_calls':client.calls,'cache_hits':client.cache_hits,**client.usage},
            limitations=['Image-token budgeting must be calibrated to the serving backend.',
                'Confidence scores are uncalibrated model self-reports.',
                'Retrieval may miss synonyms and implicit relationships; configure domain aliases.',
                'Small VLMs can misread plots, tables, scales and diagram arrows.',
                'No global engineering consistency proof or automatic proposal ranking.'])
        write_report(data,args.out)
        incomplete = any(r['status']!='complete' for r in coverage) or not left or not right or data['retrieval']['omitted_by_pair_limit']>0 or any(f.get('processing_error') for f in data['findings'])
        print(f"Report: {args.out/'report.html'}" + (' (incomplete source coverage)' if incomplete else ''))
        # 2 makes automation aware of incomplete processing; uncertainty still appears
        # in the report even when all tasks completed successfully.
        return 2 if incomplete else 0
    except (OSError, ValueError, RuntimeError) as e:
        print(f'Error: {e}',file=sys.stderr)
        return 1

def register_sources(paths):
    """Each path is a single-file source; returns (sources, files) in path order."""
    sources, files = [], []
    names = [p.name for p in paths]
    for number, path in enumerate(paths, 1):
        sid = f's{number}'
        name = path.name if names.count(path.name) == 1 else f'{path.name} [{sid}]'
        sources.append(Source(id=sid, name=name, kind='file'))
        files.append(FileRef(source=sid, path=path.name, content=content_id(path.read_bytes(), path.name)))
    return sources, files

if __name__ == '__main__':
    sys.exit(main())

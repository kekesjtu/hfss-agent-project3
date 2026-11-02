"""Normalize terminal report names for existing scalar/pattern analysis."""
from pathlib import Path
import json,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robust_summary import summary
run=Path(sys.argv[1])
result=json.loads((run/'result.json').read_text(encoding='utf8'))
if result.get('success'):
    for filename in ['sparameters.csv','sparameters_discrete.csv']:
        p=run/filename
        if not p.exists():continue
        text=p.read_text(encoding='utf-8-sig')
        original=p.with_name(p.stem+'_terminal.csv')
        if not original.exists():original.write_text(text,encoding='utf8')
        text=re.sub(r'St\([^,()]+,[^,()]+\)','S(P1,P1)',text)
        p.write_text(text,encoding='utf8')
    print(json.dumps(summary(run),indent=2))
else:
    # Keep convergence and mesh evidence from failed runs, without inventing
    # frequency data that the solver did not export.
    print(json.dumps(summary(run),indent=2))

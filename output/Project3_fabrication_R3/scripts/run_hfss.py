"""Run the nominal R3 model from its saved argument configuration."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--show-command', action='store_true')
    args = parser.parse_args()
    scripts = Path(__file__).resolve().parent
    arguments = json.loads((scripts / 'r3_hfss.json').read_text(encoding='utf8'))['arguments']
    command = [sys.executable, str(scripts / 'hfss_model.py'), *arguments]
    if args.show_command:
        print(subprocess.list2cmdline(command))
        return 0
    return subprocess.call(command, cwd=scripts.parents[2])

if __name__ == '__main__':
    raise SystemExit(main())

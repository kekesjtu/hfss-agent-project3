"""Package only the ten manufacturing layers and drill file at ZIP root."""
from pathlib import Path
import argparse
import zipfile

SUFFIXES = ['F_Cu.gtl', 'In1_Cu.g1', 'In2_Cu.g2', 'B_Cu.gbl',
            'F_Mask.gts', 'B_Mask.gbs', 'F_Silkscreen.gto', 'B_Silkscreen.gbo',
            'Edge_Cuts.gm1']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    files = [args.directory / 'Gerber' / ('Project3_array_R3-' + suffix) for suffix in SUFFIXES]
    files.append(args.directory / 'Gerber/Project3_array_R3.drl')
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    target = args.directory / 'Project3_R3_JLC_Gerber.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.name)
    print(target)

if __name__ == '__main__':
    main()

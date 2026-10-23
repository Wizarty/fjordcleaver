"""Build an isolated YouTube Playables submission ZIP; does not publish or submit it."""
import argparse
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[1]
SDK = '<script src="https://www.youtube.com/game_api/v1"></script>'

def build(output):
    source = (ROOT / 'index.html').read_text()
    assert 'fonts.googleapis.com' not in source and 'fonts.gstatic.com' not in source
    assert '<script src=' not in source, 'Review unexpected external scripts before packaging'
    source = source.replace('<head>', '<head>\n  ' + SDK + '\n  <script>window.__YOUTUBE_PLAYABLES_BUILD__ = true;</script>', 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr('index.html', source)
        package.write(ROOT / 'THIRD_PARTY_NOTICES.txt', 'THIRD_PARTY_NOTICES.txt')
    print(f'{output} ({output.stat().st_size:,} bytes)')
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'artifacts' / 'fjordcleaver-playables.zip')
    build(parser.parse_args().output)

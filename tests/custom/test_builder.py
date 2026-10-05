"""Offline regression checks for the fork's playlist builder."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
GOOD = '#EXTM3U\n#EXTINF:-1,Example\nhttps://example.org/live.m3u8\n'


class BuilderTests(unittest.TestCase):
    def run_builder(self, source, custom=GOOD, fallback=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            (root / 'custom2').mkdir()
            (root / 'bin').mkdir()
            for name in ['build-combined-m3u.sh', 'validate-custom-playlist.py']:
                shutil.copy(ROOT / 'scripts' / name, root / 'scripts' / name)
            (root / 'custom2/my.m3u').write_text(custom)
            (root / 'custom2/combined.m3u').write_text('previous playlist')
            (root / 'source').write_text(source)
            (root / 'fallback').write_text(fallback if fallback is not None else source)
            curl = root / 'bin/curl'
            curl.write_text('''#!/usr/bin/env python3
import pathlib, sys
args = sys.argv[1:]
if '-o' not in args or args[args.index('-o') + 1] == '/dev/null':
    sys.exit(1)
source = 'fallback' if any('gitlab.io' in a for a in args) else 'source'
pathlib.Path(args[args.index('-o') + 1]).write_bytes(pathlib.Path(source).read_bytes())
''')
            curl.chmod(0o755)
            result = subprocess.run(['bash', 'scripts/build-combined-m3u.sh'], cwd=root,
                                    env={**os.environ, 'PATH': str(root / 'bin') + ':' + os.environ['PATH']},
                                    capture_output=True, text=True)
            output = (root / 'custom2/combined.m3u').read_text()
            self.assertEqual(list((root / 'custom2').glob('.combined.*')), [])
            return result, output

    def test_good_playlist_has_no_log_text(self):
        result, output = self.run_builder(GOOD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Including', output)
        self.assertEqual(output.count('#EXTM3U'), 1)
        self.assertEqual(output.count('#EXTINF:'), 2)

    def test_invalid_download_uses_fallback(self):
        result, output = self.run_builder('<html>unavailable</html>', fallback=GOOD)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('#EXTINF:', output)

    def test_bad_sources_preserve_previous_playlist(self):
        result, output = self.run_builder('<html>unavailable</html>')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, 'previous playlist')

    def test_invalid_custom_preserves_previous_playlist(self):
        result, output = self.run_builder(GOOD, custom='#EXTM3U\nIncluding custom2/my.m3u\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, 'previous playlist')

    def test_missing_stream_is_rejected(self):
        result, output = self.run_builder('#EXTM3U\n#EXTINF:-1,Missing\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, 'previous playlist')

    def test_unavailable_hls_preserves_dash(self):
        url = 'https://viamotionhsi.netplus.ch/live/eds/example/browser-dash/example.mpd'
        result, output = self.run_builder('#EXTM3U\n#EXTINF:-1,Example\n' + url + '\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(url, output)


if __name__ == '__main__':
    unittest.main()

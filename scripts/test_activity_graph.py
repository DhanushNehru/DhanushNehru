"""Offline regression tests for graph captions and rotation."""
import contextlib
import datetime as dt
import io
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import activity_graph as graph


class GraphCaptionTests(unittest.TestCase):
    def days(self, count, zero=False):
        start = dt.date(2025, 10, 1)
        return [((start + dt.timedelta(days=i)).isoformat(), 0 if zero else i % 17)
                for i in range(count)]

    def caption(self, svg):
        root = ET.fromstring(svg)
        ns = {'svg': 'http://www.w3.org/2000/svg'}
        matches = [t for t in root.findall('.//svg:text', ns)
                   if 'contributions in the last' in (t.text or '')]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].get('fill'), '#58a6ff')
        self.assertEqual(matches[0].get('font-size'), '13')
        self.assertEqual(matches[0].get('font-weight'), 'bold')
        return matches[0].text

    def test_captions_use_the_exact_data_window(self):
        for count in (365, 366, 367):
            for zero in (False, True):
                days = self.days(count, zero)
                full = '%d contributions in the last %d days' % (sum(c for _, c in days), count)
                for maker in (graph.make_snake, graph.make_skyline):
                    with self.subTest(count=count, zero=zero, maker=maker.__name__):
                        self.assertEqual(self.caption(maker(days)), full)
                last = days[-31:]
                self.assertEqual(self.caption(graph.make_chart(days)),
                                 '%d contributions in the last 31 days' % sum(c for _, c in last))

    def test_each_rotation_copy_matches_its_graph(self):
        days = self.days(367)
        for index, name in enumerate(graph.NAMES):
            with tempfile.TemporaryDirectory() as out, self.subTest(index=index):
                argv = ['activity_graph.py', '--user', 'example', '--out', out, '--index', str(index)]
                with patch.object(graph, 'get_days', return_value=days), patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
                    graph.main()
                self.assertEqual((Path(out) / 'current.svg').read_bytes(),
                                 (Path(out) / (name + '.svg')).read_bytes())
                for variant in graph.NAMES:
                    self.caption((Path(out) / (variant + '.svg')).read_text())


if __name__ == '__main__':
    unittest.main()

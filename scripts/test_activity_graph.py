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


class RotationStateTests(unittest.TestCase):
    now = dt.datetime(2026, 10, 7, 13, 0, tzinfo=dt.timezone.utc)

    def previous(self, directory, name="snake", state=True):
        import json
        (Path(directory) / 'current.svg').write_text('<title>Contribution %s</title>' % name)
        if state:
            (Path(directory) / 'rotation.json').write_text(json.dumps({'current': name}))

    def test_first_publication_starts_with_snake(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(graph.rotation_index(d, '', self.now), 0)

    def test_twenty_four_hour_guard_and_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            self.previous(d)
            for elapsed in (0, 1, 3600, 10800, 43200, 86399, -3600):
                stamp = (self.now - dt.timedelta(seconds=elapsed)).isoformat()
                self.assertIsNone(graph.rotation_index(d, stamp, self.now))
            self.assertEqual(graph.rotation_index(d, '2026-10-06T13:00:00Z', self.now), 1)

    def test_delayed_runs_advance_one_design_not_clock_slot(self):
        with tempfile.TemporaryDirectory() as d:
            for index, name in enumerate(graph.NAMES):
                self.previous(d, name)
                for delay in (24, 25, 48, 72):
                    stamp = (self.now - dt.timedelta(hours=delay)).isoformat()
                    self.assertEqual(graph.rotation_index(d, stamp, self.now), (index + 1) % 3)

    def test_legacy_migration_for_each_design(self):
        with tempfile.TemporaryDirectory() as d:
            for index, name in enumerate(graph.NAMES):
                maker = {"snake": graph.make_snake, "chart": graph.make_chart,
                         "skyline": graph.make_skyline}[name]
                days = GraphCaptionTests().days(368)
                (Path(d) / 'current.svg').write_text(maker(days))
                self.assertEqual(graph.rotation_index(d, '2026-10-06T10:00:00Z', self.now), (index + 1) % 3)

    def test_invalid_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            self.previous(d, 'unknown')
            with self.assertRaises(ValueError):
                graph.rotation_index(d, '2026-10-07T10:00:00Z', self.now)
            self.previous(d)
            for stamp in ('', 'invalid', '2026-10-07T10:00:00'):
                with self.assertRaises(ValueError):
                    graph.rotation_index(d, stamp, self.now)

    def test_early_check_does_not_fetch_or_write(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out:
            self.previous(d)
            stamp = dt.datetime.now(dt.timezone.utc).isoformat()
            argv = ['activity_graph.py', '--user', 'example', '--out', out,
                    '--previous-dir', d, '--previous-published-at', stamp]
            with patch.object(graph, 'get_days') as fetch, patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
                graph.main()
            fetch.assert_not_called()
            self.assertEqual(list(Path(out).iterdir()), [])

    def test_failed_generation_does_not_write_new_state(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as out:
            self.previous(d)
            old = (Path(d) / 'rotation.json').read_bytes()
            argv = ['activity_graph.py', '--user', 'example', '--out', out,
                    '--previous-dir', d, '--previous-published-at', '2020-01-01T00:00:00Z']
            with patch.object(graph, 'get_days', side_effect=RuntimeError('offline')), patch('sys.argv', argv):
                with self.assertRaises(RuntimeError):
                    graph.main()
            self.assertFalse((Path(out) / 'rotation.json').exists())
            self.assertEqual((Path(d) / 'rotation.json').read_bytes(), old)


if __name__ == '__main__':
    unittest.main()

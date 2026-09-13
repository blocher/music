from django.test import SimpleTestCase

from catalog.lyrics import parse_lrc, to_lrc


class LyricsTests(SimpleTestCase):
    def test_lrc_round_trip_orders_cues_and_sets_end_times(self):
        cues = parse_lrc("[00:10.25]Second line\n[00:01.50]First line")

        self.assertEqual([cue["text"] for cue in cues], ["First line", "Second line"])
        self.assertEqual(cues[0]["start_ms"], 1500)
        self.assertEqual(cues[0]["end_ms"], 10249)
        self.assertEqual(to_lrc(cues), "[00:01.50]First line\n[00:10.25]Second line")

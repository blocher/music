from django.test import SimpleTestCase

from catalog.lyrics import align_transcription_to_lyrics, normalize_suno_alignment, parse_lrc, to_lrc


class LyricsTests(SimpleTestCase):
    def test_lrc_round_trip_orders_cues_and_sets_end_times(self):
        cues = parse_lrc("[00:10.25]Second line\n[00:01.50]First line")

        self.assertEqual([cue["text"] for cue in cues], ["First line", "Second line"])
        self.assertEqual(cues[0]["start_ms"], 1500)
        self.assertEqual(cues[0]["end_ms"], 10249)
        self.assertEqual(to_lrc(cues), "[00:01.50]First line\n[00:10.25]Second line")

    def test_suno_seconds_are_normalized_to_editor_milliseconds(self):
        cues, details = normalize_suno_alignment(
            {
                "hoot_cer": 0.08,
                "aligned_lyrics": [
                    {
                        "start_s": 1.25,
                        "end_s": 3.5,
                        "text": "Hello family",
                        "words": [{"word": "Hello", "start_s": 1.25, "end_s": 1.8}],
                    }
                ],
            }
        )

        self.assertEqual(cues[0]["start_ms"], 1250)
        self.assertEqual(cues[0]["end_ms"], 3500)
        self.assertEqual(cues[0]["words"][0]["start_ms"], 1250)
        self.assertAlmostEqual(details["confidence"], 0.92)

    def test_openai_words_are_mapped_to_canonical_lyric_lines(self):
        cues, confidence = align_transcription_to_lyrics(
            {
                "words": [
                    {"word": "hello", "start": 1.0, "end": 1.4},
                    {"word": "family", "start": 1.5, "end": 2.0},
                    {"word": "sing", "start": 3.0, "end": 3.4},
                    {"word": "along", "start": 3.5, "end": 4.0},
                ]
            },
            "Hello family\nSing along",
        )

        self.assertEqual([cue["start_ms"] for cue in cues], [1000, 3000])
        self.assertEqual(cues[1]["end_ms"], 4000)
        self.assertEqual(confidence, 1.0)

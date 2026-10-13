"""The text_cuts lever: a text block too long for one task is cut after a sentence's end, and a text layer at a
word's end, rather than where the bytes run out."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.tasks import cut_at_word, split_at_ends, split_utf8

PROSE = ("The telescope's primary mirror is 4 m across. This focus is shared by the coronagraph and the starshade "
         "instrument; each takes the beam in turn. Détecteur EMCCD read at 1 kHz.")

class TextCuts(unittest.TestCase):
    def test_chunks_end_at_sentence_ends_and_drop_nothing(self):
        chunks = list(split_at_ends(PROSE, 80))
        self.assertEqual("".join(chunks), PROSE)
        self.assertTrue(all(len(c.encode()) <= 80 for c in chunks))
        self.assertTrue(chunks[0].endswith("across."))
        self.assertTrue(chunks[1].endswith("instrument;"), chunks)

    def test_without_a_sentence_end_a_chunk_ends_at_a_word(self):
        text = "word " * 40
        chunks = list(split_at_ends(text, 50))
        self.assertEqual("".join(chunks), text)
        self.assertTrue(all(c.rstrip().endswith("word") for c in chunks))

    def test_a_long_word_is_cut_where_the_bytes_run_out(self):
        text = "x" * 130
        self.assertEqual(list(split_at_ends(text, 50)), list(split_utf8(text, 50)))

    def test_short_text_is_one_chunk(self):
        self.assertEqual(list(split_at_ends("A short note.", 50)), ["A short note."])

    def test_a_layer_is_cut_at_a_word(self):
        self.assertEqual(cut_at_word("defined in the Wind Energy report", 16), "defined in the")
        self.assertEqual(cut_at_word("short", 16), "short")
        self.assertEqual(cut_at_word("x" * 30, 16), "x" * 16)

    def test_the_lever_chooses_the_cut(self):
        self.assertEqual(list(Settings().split_text(PROSE, 120)), list(split_utf8(PROSE, 120)))
        self.assertEqual(list(Settings(text_cuts="sentences").split_text(PROSE, 120)), list(split_at_ends(PROSE, 120)))
        layer = "defined in the Wind Energy report"
        self.assertEqual(Settings().cut_layer(layer, 16), layer[:16])
        self.assertEqual(Settings(text_cuts="sentences").cut_layer(layer, 16), "defined in the")

if __name__ == "__main__":
    unittest.main()

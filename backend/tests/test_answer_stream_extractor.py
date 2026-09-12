"""
AnswerStreamExtractor incrementally pulls the growing "answer" string out
of a raw {"answer": "...", "cited_question_ids": [...]} token stream so the
chat streaming endpoint can show it to the user as it's generated, without
ever exposing a half-formed JSON fragment. These tests feed it one
character/chunk at a time (and split right on escape-sequence boundaries)
to prove chunk boundaries never corrupt the decoded text.
"""
from app.chat.rag import AnswerStreamExtractor, _decode_partial_json_string


def feed_all(extractor: AnswerStreamExtractor, chunks: list[str]) -> str:
    return "".join(extractor.feed(chunk) for chunk in chunks)


class TestDecodePartialJsonString:
    def test_decodes_plain_text_up_to_closing_quote(self):
        text, closed = _decode_partial_json_string('hello world"', 0)
        assert (text, closed) == ("hello world", True)

    def test_returns_not_closed_when_quote_hasnt_arrived(self):
        text, closed = _decode_partial_json_string("hello wor", 0)
        assert (text, closed) == ("hello wor", False)

    def test_decodes_simple_escapes(self):
        text, closed = _decode_partial_json_string('line1\\nline2\\t\\"quoted\\""', 0)
        assert (text, closed) == ('line1\nline2\t"quoted"', True)

    def test_decodes_unicode_escape(self):
        text, closed = _decode_partial_json_string('caf\\u00e9"', 0)
        assert (text, closed) == ("café", True)

    def test_stops_before_a_trailing_incomplete_escape(self):
        # A backslash at the very end could be the start of an escape we
        # haven't fully received yet — must not guess.
        text, closed = _decode_partial_json_string("abc\\", 0)
        assert (text, closed) == ("abc", False)

    def test_stops_before_a_trailing_incomplete_unicode_escape(self):
        text, closed = _decode_partial_json_string("abc\\u00e", 0)
        assert (text, closed) == ("abc", False)


class TestAnswerStreamExtractor:
    def test_extracts_answer_text_as_chunks_arrive(self):
        extractor = AnswerStreamExtractor()
        chunks = ['{"answer": "Nagarro', " asked about", ' virtual threads."', ', "cited_question_ids": ["q1"]}']

        result = feed_all(extractor, chunks)

        assert result == "Nagarro asked about virtual threads."
        assert extractor.buffer == "".join(chunks)

    def test_never_emits_anything_before_the_answer_field_is_found(self):
        extractor = AnswerStreamExtractor()
        # Nothing should come out while only whitespace/opening brace has arrived.
        assert extractor.feed("{") == ""
        assert extractor.feed("  ") == ""
        assert extractor.feed('"answer"') == ""
        assert extractor.feed(': "') == ""
        assert extractor.feed("Hi") == "Hi"

    def test_handles_an_escaped_quote_inside_the_answer(self):
        extractor = AnswerStreamExtractor()
        chunks = ['{"answer": "She said \\"hello\\" to me.", "cited_question_ids": []}']
        assert feed_all(extractor, chunks) == 'She said "hello" to me.'

    def test_escape_sequence_split_across_two_chunks_is_not_corrupted(self):
        extractor = AnswerStreamExtractor()
        # The backslash arrives in one chunk, the "n" that completes \n in
        # the next — a naive per-chunk decoder would mis-decode this.
        chunks = ['{"answer": "line1\\', 'nline2"', ', "cited_question_ids": []}']
        assert feed_all(extractor, chunks) == "line1\nline2"

    def test_unicode_escape_split_across_chunks_is_not_corrupted(self):
        extractor = AnswerStreamExtractor()
        chunks = ['{"answer": "caf\\u00', 'e9 society"', ", ...}"]
        assert feed_all(extractor, chunks) == "café society"

    def test_stops_emitting_once_the_answer_string_closes(self):
        extractor = AnswerStreamExtractor()
        extractor.feed('{"answer": "Done."')
        # Whatever comes after the closing quote (the cited_question_ids
        # array) must never leak into the displayed answer text.
        after = extractor.feed(', "cited_question_ids": ["q1", "q2"]}')
        assert after == ""

    def test_never_yields_duplicate_text_across_feeds(self):
        extractor = AnswerStreamExtractor()
        seen = ""
        for chunk in ['{"answer": "a', "b", "c", 'd"', ", ...}"]:
            seen += extractor.feed(chunk)
        assert seen == "abcd"

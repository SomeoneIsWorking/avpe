import contextlib
from dataclasses import replace
import io
import json
import struct
import unittest
from unittest.mock import patch

from avpe.tbf_archive import Limits, search_archive
from tools.search_tbf import main


def chunk(tag: bytes, payload: bytes) -> bytes:
    return tag + struct.pack("<I", len(payload)) + payload + bytes(len(payload) & 1)


def archive(*children: bytes) -> bytes:
    return chunk(b"RIFF", b"TBFF" + b"".join(children))


# Two literal words, then the BWJ terminator. The existing decoder owns semantics.
COMPRESSED_QUIT = struct.pack("<I5H", 4, 0x07FF, 0x2000, 0x7571, 0x3CF5, 0)
QUIT = bytes.fromhex("7175f53c")


class TbfArchiveTests(unittest.TestCase):
    def test_searches_compressed_and_plain_payloads_with_exact_provenance(self) -> None:
        data = archive(chunk(b"LIST", b"TBD2" + chunk(
            b"LIST", b"PS2 " + chunk(b"DATX", COMPRESSED_QUIT))),
            chunk(b"EXTA", b"Main_Quit\0"))
        result = search_archive(data, (QUIT, b"Main_Quit", b"absent"))
        self.assertEqual(result["chunks"], 5)
        self.assertEqual(result["compressed_chunks"], 1)
        self.assertEqual(result["decoded_payload_bytes"], 14)
        self.assertEqual([item["matches"] for item in result["patterns"]], [1, 1, 0])
        self.assertEqual(result["patterns"][0]["locations"], [{
            "chunk_offset": 36, "tag": "DATX", "payload_offset": 0,
            "containers": [0, 12, 24],
        }])

    def test_location_cap_does_not_cap_match_count_or_overlapping_matches(self) -> None:
        result = search_archive(archive(chunk(b"DATA", b"aaaa")), (b"aa",),
                                replace(Limits(), locations=1))
        self.assertEqual(result["patterns"][0]["matches"], 3)
        self.assertEqual(len(result["patterns"][0]["locations"]), 1)

    def test_refuses_missing_empty_and_unsupported_corpora(self) -> None:
        for data in (b"", archive(), archive(chunk(b"DATA", b"")),
                     archive(chunk(b"NOPE", b"xx")), archive(chunk(b"LIST", b"WIND"))):
            with self.subTest(data=data), self.assertRaises(ValueError):
                search_archive(data, (b"x",))

    def test_refuses_truncated_sizes_headers_and_missing_padding(self) -> None:
        valid = archive(chunk(b"DATA", b"x"))
        malformed = [valid[:-1], valid + b"x", archive(b"x"),
                     archive(b"DATA" + struct.pack("<I", 20) + b"xx"),
                     archive(b"DATA" + struct.pack("<I", 1) + b"x" + b"DATA0000")]
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(ValueError):
                search_archive(data, (b"x",))

    def test_refuses_wrong_expanded_size_trailing_compressed_data_and_truncation(self) -> None:
        for payload in (struct.pack("<I", 6) + COMPRESSED_QUIT[4:],
                        COMPRESSED_QUIT + b"\0\0", COMPRESSED_QUIT[:-2], b"\0" * 4):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                search_archive(archive(chunk(b"DATX", payload)), (QUIT,))

    def test_enforces_every_resource_bound(self) -> None:
        data = archive(chunk(b"DATX", COMPRESSED_QUIT), chunk(b"DATA", QUIT))
        for field, value in (("archive_bytes", 8), ("chunk_bytes", 2),
                             ("decoded_bytes", 6), ("chunks", 2), ("depth", 1)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                search_archive(data, (QUIT,), replace(Limits(), **{field: value}))
        with self.assertRaises(ValueError):
            search_archive(data, (QUIT,), replace(Limits(), locations=0))

    def test_refuses_missing_empty_or_duplicate_patterns(self) -> None:
        for patterns in ((), (b"",), (QUIT, QUIT)):
            with self.subTest(patterns=patterns), self.assertRaises(ValueError):
                search_archive(archive(chunk(b"DATA", QUIT)), patterns)

    def test_cli_reports_both_answers_through_the_real_decoder(self) -> None:
        output = io.StringIO()
        with patch("sys.argv", ["search_tbf", "fixture.tbf", "--hex", QUIT.hex(),
                                "--text", "absent"]), patch(
            "pathlib.Path.open", return_value=io.BytesIO(archive(chunk(b"DATX", COMPRESSED_QUIT)))
        ), contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        result = json.loads(output.getvalue())
        self.assertEqual([item["matches"] for item in result["patterns"]], [1, 0])
        self.assertEqual(result["decoded_payload_bytes"], 4)

    def test_cli_missing_file_is_an_error_not_zero_matches(self) -> None:
        with patch("sys.argv", ["search_tbf", "missing.tbf", "--text", "QuitGame"]), patch(
            "pathlib.Path.open", side_effect=FileNotFoundError("missing.tbf")
        ), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code, 2)

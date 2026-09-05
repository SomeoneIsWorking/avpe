import copy
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from avpe.bios_inventory import (
    INVENTORY_SCHEMA,
    combine_bios_inventories,
    summarize_bios_artifact,
)
from avpe.native_bios_probe import bios_trace_is_verified
from tools.analyze_bios_traces import main as analyze_main


def make_result_summary(
    first: int,
    *,
    last: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
    changes: int = 0,
    encoding: str = "s32",
) -> dict[str, object]:
    last = first if last is None else last
    minimum = min(first, last) if minimum is None else minimum
    maximum = max(first, last) if maximum is None else maximum
    return {
        "encoding": encoding,
        "first": first,
        "last": last,
        "min": minimum,
        "max": maximum,
        "changes": changes,
    }


def make_artifact() -> dict[str, object]:
    return {
        "phase": "statefile_to_menu",
        "operation": "menu_down",
        "statefile": "pause-menu.p2s",
        "trace": {
            "schema": "avpe-bios-trace-v7",
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "ee_syscall_pairing": {
                "entries": 0,
                "returns": 0,
                "pending": 0,
                "sequence_errors": 0,
                "overflow": 0,
            },
            "iop_import_pairing": {
                "entries": 0,
                "returns": 0,
                "pending": 0,
                "overflow": 0,
            },
            "events": [
                {
                    "sequence": 1,
                    "kind": "ee_syscall",
                    "number": 127,
                    "name": "GetMemorySize",
                    "first_arguments": [0, 1, 2, 3],
                    "outcome": "direct",
                    "result_valid": True,
                    "result_summary": make_result_summary(0),
                    "result_expected": True,
                    "return_expected": True,
                },
                {
                    "sequence": 2,
                    "kind": "import",
                    "library": "ioman",
                    "ordinal": 6,
                    "function": "open",
                    "first_arguments": [0, 1, 2, 3],
                    "outcome": "hle",
                    "result_valid": True,
                    "result_summary": make_result_summary(3),
                    "hle_available": True,
                    "debug_available": False,
                },
                {
                    "sequence": 3,
                    "kind": "module",
                    "module": "loadcore",
                    "operation": "register",
                    "version_major": 1,
                    "version_minor": 2,
                },
                {
                    "sequence": 4,
                    "kind": "exception",
                    "domain": "ee",
                    "code": 32,
                    "pc": 4096,
                    "branch_delay": False,
                    "transition": {"status_before": 0x10001, "status_after": 0x10003,
                                   "cause_after": 32, "epc_after": 4096, "vector_pc": 0x80000180},
                },
                {
                    "sequence": 5,
                    "kind": "timer",
                    "domain": "iop",
                    "counter": 2,
                    "overflow": True,
                    "count": 4,
                    "target": 4,
                    "cycle": 100,
                    "delivered": False,
                },
                {
                    "sequence": 6,
                    "kind": "interrupt",
                    "number": 2,
                    "name": "timer",
                    "handler": 8192,
                },
                {"sequence": 7, "kind": "rpc", "rpc_id": 0x1234},
            ],
        },
    }


class BiosInventoryTests(unittest.TestCase):
    def test_summarizes_services_and_runtime_categories(self) -> None:
        summary = summarize_bios_artifact(make_artifact())

        self.assertEqual(summary["schema"], INVENTORY_SCHEMA)
        self.assertEqual(summary["event_count"], 7)
        self.assertEqual(summary["event_counts"]["exception"], 1)
        self.assertEqual(summary["services"]["ee_syscall"][0]["name"], "GetMemorySize")
        self.assertEqual(summary["services"]["import"][0]["function"], "open")
        self.assertEqual(
            summary["services"]["ee_syscall"][0]["outcomes"], {"direct": 1}
        )
        self.assertEqual(
            summary["services"]["ee_syscall"][0]["observed_result_calls"], 1
        )
        self.assertEqual(
            summary["services"]["ee_syscall"][0]["unobserved_result_calls"], 0
        )
        self.assertEqual(summary["services"]["module"][0]["operations"], ["register"])
        self.assertEqual(summary["exceptions"]["identities"], [{
            "domain": "ee", "code": 32, "pc": 4096, "branch_delay": False,
            "event_count": 1, "occurrences": 1,
            "transition": make_artifact()["trace"]["events"][3]["transition"],
        }])
        self.assertEqual(summary["timers"]["identities"], [{
            "domain": "iop", "counter": 2, "overflow": True, "delivered": False,
            "event_count": 1, "occurrences": 1,
            "first_sample": {"count": 4, "target": 4, "cycle": 100},
        }])
        json.dumps(summary)

    def test_runtime_identities_preserve_domains_outcomes_and_occurrence_denominators(self) -> None:
        artifact = make_artifact()
        events = artifact["trace"]["events"]
        events[3]["calls"] = 100
        events[4]["calls"] = 50
        for changes in ({"calls": 7, "cycle": 300},
                        {"calls": 3, "delivered": True},
                        {"calls": 9, "domain": "ee"}):
            duplicate = dict(events[4], **changes, sequence=len(events) + 1)
            events.append(duplicate)
        summary = summarize_bios_artifact(artifact)
        self.assertEqual(summary["exceptions"]["occurrences"], 100)
        timers = summary["timers"]
        self.assertEqual((timers["event_count"], timers["occurrences"]), (4, 69))
        identities = timers["identities"]
        self.assertEqual([(item["domain"], item["delivered"], item["occurrences"])
                          for item in identities], [("ee", False, 9), ("iop", False, 57), ("iop", True, 3)])
        self.assertEqual(identities[1]["event_count"], 2)
        self.assertEqual(identities[1]["first_sample"]["cycle"], 100)

    def test_exception_branch_delay_remains_part_of_identity(self) -> None:
        artifact = make_artifact()
        events = artifact["trace"]["events"]
        events.append(dict(events[3], branch_delay=True, calls=11, sequence=8))
        summary = summarize_bios_artifact(artifact)["exceptions"]
        self.assertEqual(summary["occurrences"], 12)
        self.assertEqual(len(summary["identities"]), 2)

    def test_runtime_malformed_fields_are_refused_by_trace_and_inventory(self) -> None:
        for index, field, values in (
            (3, "domain", ["unknown", None]), (3, "pc", [-1, 1 << 32, True, None]),
            (3, "code", [-1, "32", None]), (3, "branch_delay", [0, None]),
            (4, "counter", [-1, True, None]), (4, "count", [-1, 1 << 64, None]),
            (4, "target", [True, None]), (4, "cycle", [-1, None]),
            (4, "overflow", [1, None]), (4, "delivered", [0, None]),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    artifact = make_artifact()
                    artifact["trace"]["events"][index][field] = value
                    self.assertFalse(bios_trace_is_verified(artifact["trace"]))
                    with self.assertRaises(ValueError):
                        summarize_bios_artifact(artifact)

    def test_exception_transitions_are_mandatory_and_preserve_identity(self) -> None:
        artifact = make_artifact()
        events = artifact["trace"]["events"]
        duplicate = copy.deepcopy(events[3])
        duplicate.update(sequence=8, calls=7)
        duplicate["transition"]["vector_pc"] = 0xBFC00380
        events.append(duplicate)
        summary = summarize_bios_artifact(artifact)["exceptions"]
        self.assertEqual(summary["occurrences"], 8)
        self.assertEqual(len(summary["identities"]), 2)
        original = make_artifact()["trace"]["events"][3]["transition"]
        malformed = [None, [], {}, dict(original, extra=0)]
        for field in original:
            malformed.append({key: value for key, value in original.items() if key != field})
            malformed.extend(dict(original, **{field: value}) for value in (-1, True, 1 << 32))
        for transition in malformed:
            with self.subTest(transition=transition):
                artifact = make_artifact()
                artifact["trace"]["events"][3]["transition"] = transition
                self.assertFalse(bios_trace_is_verified(artifact["trace"]))
                with self.assertRaises(ValueError):
                    summarize_bios_artifact(artifact)
        artifact = make_artifact()
        artifact["trace"]["schema"] = "avpe-bios-trace-v6"
        self.assertFalse(bios_trace_is_verified(artifact["trace"]))

    def test_absent_runtime_events_report_zero_observations(self) -> None:
        artifact = make_artifact()
        artifact["trace"]["events"] = artifact["trace"]["events"][:1]
        summary = summarize_bios_artifact(artifact)
        for kind in ("exceptions", "timers"):
            self.assertEqual(summary[kind]["event_count"], 0)
            self.assertEqual(summary[kind]["occurrences"], 0)
            self.assertEqual(summary[kind]["identities"], [])
        self.assertEqual(summary["timers"]["measurement"], "counter_source_irq_assertion")
        self.assertEqual(summary["exceptions"]["measurement"], "cpu_exception_transition")

    def test_cli_preserves_positive_and_negative_timer_source_outcomes(self) -> None:
        artifact = make_artifact()
        events = artifact["trace"]["events"]
        events[4]["calls"] = 5
        events.append(dict(events[4], sequence=8, delivered=True, calls=19))
        output = io.StringIO()
        with patch("sys.argv", ["analyze_bios_traces", "fixture.json"]), patch(
            "pathlib.Path.read_text", return_value=json.dumps(artifact)
        ), contextlib.redirect_stdout(output):
            self.assertEqual(analyze_main(), 0)
        report = json.loads(output.getvalue())
        identities = report["captures"][0]["timers"]["identities"]
        self.assertEqual([(item["delivered"], item["occurrences"]) for item in identities],
                         [(False, 5), (True, 19)])

    def test_repeated_service_identity_is_counted_without_losing_results(self) -> None:
        artifact = make_artifact()
        events = artifact["trace"]["events"]
        events.append(copy.deepcopy(events[0]))
        events[-1]["sequence"] = 8
        events[-1]["result_summary"] = make_result_summary(-1)

        summary = summarize_bios_artifact(artifact)

        syscall = summary["services"]["ee_syscall"][0]
        self.assertEqual(syscall["calls"], 2)
        self.assertEqual(
            syscall["result_observations"],
            {
                "encoding": "s32",
                "samples": [-1, 0],
                "min": -1,
                "max": 0,
                "transitions_within_trace_events": 0,
            },
        )

    def test_summarizes_bounded_changing_results_without_claiming_all_values(self) -> None:
        artifact = make_artifact()
        imported = artifact["trace"]["events"][1]
        imported["calls"] = 10000
        imported["result_summary"] = make_result_summary(
            10, last=500, minimum=0, maximum=9999, changes=9876
        )

        summary = summarize_bios_artifact(artifact)

        observations = summary["services"]["import"][0]["result_observations"]
        self.assertEqual(observations["samples"], [0, 10, 500, 9999])
        self.assertEqual(observations["min"], 0)
        self.assertEqual(observations["max"], 9999)
        self.assertEqual(observations["transitions_within_trace_events"], 9876)

    def test_counts_oracle_results_as_unobserved_without_inventing_values(self) -> None:
        artifact = make_artifact()
        syscall = artifact["trace"]["events"][0]
        syscall["outcome"] = "bios"
        syscall["result_valid"] = False
        del syscall["result_summary"]
        artifact["trace"]["ee_syscall_pairing"].update(
            {"entries": 1, "pending": 1}
        )
        imported = artifact["trace"]["events"][1]
        imported["outcome"] = "oracle"
        imported["result_valid"] = False
        del imported["result_summary"]
        imported.update(
            {"first_stack_pointer": 0x001FF000, "first_resume_pc": 0x00010200}
        )
        artifact["trace"]["iop_import_pairing"].update(
            {"entries": 1, "pending": 1}
        )

        summary = summarize_bios_artifact(artifact)

        syscall_summary = summary["services"]["ee_syscall"][0]
        import_summary = summary["services"]["import"][0]
        self.assertIsNone(syscall_summary["result_observations"])
        self.assertEqual(syscall_summary["observed_result_calls"], 0)
        self.assertEqual(syscall_summary["unobserved_result_calls"], 1)
        self.assertEqual(import_summary["outcomes"], {"oracle": 1})
        self.assertEqual(import_summary["unobserved_result_calls"], 1)

    def test_pairs_iop_oracle_return_results_with_the_entry_identity(self) -> None:
        artifact = make_artifact()
        imported = artifact["trace"]["events"][1]
        imported["outcome"] = "oracle"
        imported["result_valid"] = False
        del imported["result_summary"]
        imported.update(
            {"first_stack_pointer": 0x001FF000, "first_resume_pc": 0x00010200}
        )
        artifact["trace"]["events"].append(
            {
                "sequence": 8,
                "kind": "iop_import_return",
                "library": "ioman",
                "ordinal": 6,
                "function": "open",
                "result_valid": True,
                "result_summary": make_result_summary(-5),
                "hle_available": True,
                "debug_available": False,
                "first_stack_pointer": 0x001FF000,
                "first_resume_pc": 0x00010200,
            }
        )
        artifact["trace"]["iop_import_pairing"].update(
            {"entries": 1, "returns": 1}
        )

        summary = summarize_bios_artifact(artifact)

        imported_summary = summary["services"]["import"][0]
        self.assertEqual(imported_summary["returned_oracle_calls"], 1)
        self.assertEqual(imported_summary["observed_result_calls"], 1)
        self.assertEqual(imported_summary["unobserved_result_calls"], 0)
        self.assertEqual(imported_summary["result_observations"]["samples"], [-5])

    def test_distinguishes_resultless_direct_calls_from_pending_bios_calls(self) -> None:
        artifact = make_artifact()
        syscall = artifact["trace"]["events"][0]
        syscall.update({"number": 100, "name": "FlushCache", "result_expected": False})
        syscall["result_valid"] = False
        del syscall["result_summary"]

        summary = summarize_bios_artifact(artifact)

        syscall_summary = summary["services"]["ee_syscall"][0]
        self.assertEqual(syscall_summary["resultless_calls"], 1)
        self.assertEqual(syscall_summary["unobserved_result_calls"], 0)
        self.assertEqual(syscall_summary["observed_result_calls"], 0)

    def test_pairs_bios_return_results_with_the_entry_identity(self) -> None:
        artifact = make_artifact()
        syscall = artifact["trace"]["events"][0]
        syscall.update({"number": 68, "name": "WaitSema", "outcome": "bios"})
        syscall["result_valid"] = False
        del syscall["result_summary"]
        artifact["trace"]["events"].append(
            {
                "sequence": 8,
                "kind": "ee_syscall_return",
                "number": 68,
                "name": "WaitSema",
                "result_expected": True,
                "result_valid": True,
                "result_summary": make_result_summary(-1),
                "first_stack_pointer": 0x01FFF000,
                "first_resume_pc": 0x00102004,
            }
        )
        artifact["trace"]["ee_syscall_pairing"].update(
            {"entries": 1, "returns": 1}
        )

        summary = summarize_bios_artifact(artifact)

        syscall_summary = summary["services"]["ee_syscall"][0]
        self.assertEqual(syscall_summary["calls"], 1)
        self.assertEqual(syscall_summary["returned_bios_calls"], 1)
        self.assertEqual(syscall_summary["observed_result_calls"], 1)
        self.assertEqual(syscall_summary["unobserved_result_calls"], 0)
        self.assertEqual(syscall_summary["result_observations"]["samples"], [-1])

    def test_distinguishes_returned_void_from_uncaptured_result(self) -> None:
        void_artifact = make_artifact()
        void_entry = void_artifact["trace"]["events"][0]
        void_entry.update(
            {
                "number": 100,
                "name": "FlushCache",
                "outcome": "bios",
                "result_valid": False,
                "result_expected": False,
            }
        )
        del void_entry["result_summary"]
        void_artifact["trace"]["events"].append(
            {
                "sequence": 8,
                "kind": "ee_syscall_return",
                "number": 100,
                "name": "FlushCache",
                "result_expected": False,
                "result_valid": False,
                "first_stack_pointer": 0x01FFF000,
                "first_resume_pc": 0x00102004,
            }
        )
        void_artifact["trace"]["ee_syscall_pairing"].update(
            {"entries": 1, "returns": 1}
        )

        void_summary = summarize_bios_artifact(void_artifact)["services"]["ee_syscall"][0]
        self.assertEqual(void_summary["resultless_calls"], 1)
        self.assertEqual(void_summary["unobserved_result_calls"], 0)

        unknown_artifact = make_artifact()
        unknown_entry = unknown_artifact["trace"]["events"][0]
        unknown_entry.update(
            {
                "number": 3,
                "name": "RFU003",
                "outcome": "bios",
                "result_valid": False,
            }
        )
        del unknown_entry["result_summary"]
        unknown_artifact["trace"]["events"].append(
            {
                "sequence": 8,
                "kind": "ee_syscall_return",
                "number": 3,
                "name": "RFU003",
                "result_expected": True,
                "result_valid": False,
                "first_stack_pointer": 0x01FFF000,
                "first_resume_pc": 0x00102004,
            }
        )
        unknown_artifact["trace"]["ee_syscall_pairing"].update(
            {"entries": 1, "returns": 1}
        )

        unknown_summary = summarize_bios_artifact(unknown_artifact)["services"]["ee_syscall"][0]
        self.assertEqual(unknown_summary["resultless_calls"], 0)
        self.assertEqual(unknown_summary["unobserved_result_calls"], 1)

    def test_summarizes_returned_u64_result(self) -> None:
        artifact = make_artifact()
        entry = artifact["trace"]["events"][0]
        entry.update(
            {
                "number": 112,
                "name": "GsGetIMR",
                "outcome": "bios",
                "result_valid": False,
            }
        )
        del entry["result_summary"]
        artifact["trace"]["events"].append(
            {
                "sequence": 8,
                "kind": "ee_syscall_return",
                "number": 112,
                "name": "GsGetIMR",
                "result_expected": True,
                "result_valid": True,
                "result_summary": make_result_summary(
                    (1 << 63) + 1, encoding="u64"
                ),
                "first_stack_pointer": 0x01FFF000,
                "first_resume_pc": 0x00102004,
            }
        )
        artifact["trace"]["ee_syscall_pairing"].update({"entries": 1, "returns": 1})

        syscall_summary = summarize_bios_artifact(artifact)["services"]["ee_syscall"][0]
        self.assertEqual(syscall_summary["observed_result_calls"], 1)
        self.assertEqual(
            syscall_summary["result_observations"]["samples"],
            [(1 << 63) + 1],
        )

    def test_counts_nonreturning_bios_control_transfers_separately(self) -> None:
        artifact = make_artifact()
        syscall = artifact["trace"]["events"][0]
        syscall.update(
            {
                "number": 5,
                "name": "ResumeIntrDispatch",
                "outcome": "bios",
                "result_valid": False,
                "result_expected": False,
                "return_expected": False,
            }
        )
        del syscall["result_summary"]

        summary = summarize_bios_artifact(artifact)

        syscall_summary = summary["services"]["ee_syscall"][0]
        self.assertEqual(syscall_summary["nonreturning_calls"], 1)
        self.assertEqual(syscall_summary["returned_bios_calls"], 0)
        self.assertEqual(syscall_summary["unobserved_result_calls"], 0)

    def test_rejects_invalid_trace_and_empty_combination(self) -> None:
        invalid = make_artifact()
        invalid["trace"]["overflow"] = 1
        with self.assertRaises(ValueError):
            summarize_bios_artifact(invalid)
        with self.assertRaises(ValueError):
            combine_bios_inventories([])

    def test_combines_capture_metadata_and_counts(self) -> None:
        first = summarize_bios_artifact(make_artifact())
        second_artifact = make_artifact()
        second_artifact["phase"] = "clean_boot_to_running"
        second = summarize_bios_artifact(second_artifact)

        combined = combine_bios_inventories([first, second])

        self.assertEqual(combined["capture_count"], 2)
        self.assertEqual(
            combined["phases"], ["clean_boot_to_running", "statefile_to_menu"]
        )
        self.assertEqual(combined["event_counts"]["timer"], 2)
        self.assertEqual(
            combined["service_kinds"],
            ["ee_syscall", "import", "interrupt", "module", "rpc"],
        )

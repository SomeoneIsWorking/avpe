import copy
import json
import unittest

from avpe.bios_inventory import (
    INVENTORY_SCHEMA,
    combine_bios_inventories,
    summarize_bios_artifact,
)


def make_artifact() -> dict[str, object]:
    return {
        "phase": "statefile_to_menu",
        "operation": "menu_down",
        "statefile": "pause-menu.p2s",
        "trace": {
            "schema": "avpe-bios-trace-v4",
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
                    "result": 0,
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
                    "result": 3,
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
        self.assertEqual(summary["exceptions"]["pcs"], {"4096": 1})
        self.assertEqual(summary["timers"]["delivered"], {"false": 1})
        json.dumps(summary)

    def test_repeated_service_identity_is_counted_without_losing_results(self) -> None:
        artifact = make_artifact()
        events = artifact["trace"]["events"]
        events.append(copy.deepcopy(events[0]))
        events[-1]["sequence"] = 8
        events[-1]["result"] = -1

        summary = summarize_bios_artifact(artifact)

        syscall = summary["services"]["ee_syscall"][0]
        self.assertEqual(syscall["calls"], 2)
        self.assertEqual(syscall["results"], [-1, 0])

    def test_counts_oracle_results_as_unobserved_without_inventing_values(self) -> None:
        artifact = make_artifact()
        syscall = artifact["trace"]["events"][0]
        syscall["outcome"] = "bios"
        syscall["result_valid"] = False
        del syscall["result"]
        artifact["trace"]["ee_syscall_pairing"].update(
            {"entries": 1, "pending": 1}
        )
        imported = artifact["trace"]["events"][1]
        imported["outcome"] = "oracle"
        imported["result_valid"] = False
        del imported["result"]
        imported.update(
            {"first_stack_pointer": 0x001FF000, "first_resume_pc": 0x00010200}
        )
        artifact["trace"]["iop_import_pairing"].update(
            {"entries": 1, "pending": 1}
        )

        summary = summarize_bios_artifact(artifact)

        syscall_summary = summary["services"]["ee_syscall"][0]
        import_summary = summary["services"]["import"][0]
        self.assertEqual(syscall_summary["results"], [])
        self.assertEqual(syscall_summary["observed_result_calls"], 0)
        self.assertEqual(syscall_summary["unobserved_result_calls"], 1)
        self.assertEqual(import_summary["outcomes"], {"oracle": 1})
        self.assertEqual(import_summary["unobserved_result_calls"], 1)

    def test_pairs_iop_oracle_return_results_with_the_entry_identity(self) -> None:
        artifact = make_artifact()
        imported = artifact["trace"]["events"][1]
        imported["outcome"] = "oracle"
        imported["result_valid"] = False
        del imported["result"]
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
                "result": -5,
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
        self.assertEqual(imported_summary["results"], [-5])

    def test_distinguishes_resultless_direct_calls_from_pending_bios_calls(self) -> None:
        artifact = make_artifact()
        syscall = artifact["trace"]["events"][0]
        syscall.update({"number": 100, "name": "FlushCache", "result_expected": False})
        syscall["result_valid"] = False
        del syscall["result"]

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
        del syscall["result"]
        artifact["trace"]["events"].append(
            {
                "sequence": 8,
                "kind": "ee_syscall_return",
                "number": 68,
                "name": "WaitSema",
                "result_expected": True,
                "result_valid": True,
                "result": -1,
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
        self.assertEqual(syscall_summary["results"], [-1])

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
        del void_entry["result"]
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
        del unknown_entry["result"]
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
        del syscall["result"]

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

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
            "schema": "avpe-bios-trace-v2",
            "enabled": True,
            "capacity": 4096,
            "overflow": 0,
            "events": [
                {
                    "sequence": 1,
                    "kind": "ee_syscall",
                    "number": 100,
                    "name": "FlushCache",
                    "first_arguments": [0, 1, 2, 3],
                    "outcome": "direct",
                    "result_valid": True,
                    "result": 0,
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
        self.assertEqual(summary["services"]["ee_syscall"][0]["name"], "FlushCache")
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
        imported = artifact["trace"]["events"][1]
        imported["outcome"] = "oracle"
        imported["result_valid"] = False
        del imported["result"]

        summary = summarize_bios_artifact(artifact)

        syscall_summary = summary["services"]["ee_syscall"][0]
        import_summary = summary["services"]["import"][0]
        self.assertEqual(syscall_summary["results"], [])
        self.assertEqual(syscall_summary["observed_result_calls"], 0)
        self.assertEqual(syscall_summary["unobserved_result_calls"], 1)
        self.assertEqual(import_summary["outcomes"], {"oracle": 1})
        self.assertEqual(import_summary["unobserved_result_calls"], 1)

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

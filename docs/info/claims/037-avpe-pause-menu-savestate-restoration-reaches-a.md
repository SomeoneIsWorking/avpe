---
id: C037
kind: claim
status: holds
created: 2026-08-31
tags:
depends: src/avpe/native_bios_probe.py#run_bios_phase, thirdparty/pcsx2/pcsx2/AVPE/NativeMenuInput.cpp
---

## Claim

AVPE pause-menu savestate restoration reaches a repeatable guest-owned completion boundary when the restored menu accepts down; two runs retained matching 28-event traces with five fully paired EE BIOS calls and zero overflow

## Evidence

scratch/control-test/bios-save-load-v4.prev.json; scratch/control-test/bios-save-load-v4.json; tests.test_control_test.ControlTestPolicyTests.test_save_load_bios_phase_uses_game_owned_menu_completion

## What would falsify it

a repeat from the same pause-menu state reaches a different event identity set, fails to complete the game-owned menu action, or leaves a pairing error, pending call, or overflow

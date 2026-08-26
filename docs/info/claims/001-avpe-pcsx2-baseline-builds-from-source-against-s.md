---
id: C001
kind: claim
status: holds
created: 2026-08-26
tags: build
depends: deps.toml
---

## Claim

AVPE: PCSX2 baseline builds from source against self-built Qt/deps in scratch/deps (upstream build-dependencies-qt.sh, designer OFF); binary at scratch/build/bin/pcsx2-qt; -testconfig with seeded -datapath exits 0

## Evidence

scratch/logs/build-deps2.log, scratch/logs/pcsx2-config.log, scratch/logs/pcsx2-build.log (865/865), scratch/logs/testconfig.log

## What would falsify it

a clean re-run of the two commands failing, or pcsx2-qt refusing the datapath on next boot

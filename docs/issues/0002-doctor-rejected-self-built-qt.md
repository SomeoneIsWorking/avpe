---
id: 2
title: Doctor rejected the accepted self-built Qt prefix
status: resolved
symptom: ./run.sh doctor accepted scratch/deps as the project Qt prefix and then reported missing system Qt development files as a blocker
state_items: S001,S012
tags: launcher,doctor,qt
created: 2026-08-26
updated: 2026-08-26
---

## Root cause

The doctor had two independent Qt authorities. Its build-output check accepted
the self-built prefix under `scratch/deps`, while a later check ignored that
prefix and required headers and CMake metadata reported by system `qtpaths6`.
The second probe contradicted the project's actual build contract.

## Resolution

The self-built prefix is the single Qt authority. Doctor now verifies both
`include/QtCore/qglobal.h` and `lib/cmake/Qt6/Qt6Config.cmake` there and reports
their two booleans when the prefix is incomplete. The duplicate system-Qt probe
was removed.

## Verification

`./run.sh doctor` reports the self-built prefix with headers and CMake config
and completes with zero blockers on the existing project checkout.

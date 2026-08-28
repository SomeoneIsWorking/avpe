---
id: C032
kind: claim
status: holds
created: 2026-08-28
tags: launcher,build
depends: src/avpe/build.py#prepare_product, src/avpe/build.py#_build_product, tests/test_build.py#ProductPreparationTests
---

## Claim

prepare_product rebuilds the current AVPE target

## Evidence

The real ./run.sh prepare path rebuilt scratch/build/bin/avpe after the preparation owner was changed to invoke the existing CMake/Ninja target even when the binary already existed. The full non-windowed verifier passed 119 Python tests, 19 production C++ tests, clang-format, and 45 clang-tidy units; unit tests cover configured and missing build-tree paths.

## What would falsify it

a source change leaves ./run.sh prepare able to return an existing stale binary without invoking the current CMake target, or the CMake target fails to produce the product binary

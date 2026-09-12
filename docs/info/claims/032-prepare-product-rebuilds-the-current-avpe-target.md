---
id: C032
kind: claim
status: holds
created: 2026-08-28
tags: launcher,build
depends: src/avpe/build.py#prepare_product, src/avpe/build.py#_build_target, tests/test_build.py#ProductPreparationTests
---

## Claim

prepare_product rebuilds the current AVPE target

## Evidence

The real non-launching preparation path rebuilt `build/bin/avpe` through the current CMake/Ninja target even when the binary already existed. The full non-windowed verifier passed 119 Python tests, 19 production C++ tests, clang-format, and 45 clang-tidy units; unit tests cover configured and missing build-tree paths. The maintainer entry point is `uv run --frozen avpe prepare`; `./run.sh` invokes the same preparation owner before opening the product.

## What would falsify it

a source change leaves `uv run --frozen avpe prepare` or the default launcher able to return an existing stale binary without invoking the current CMake target, or the CMake target fails to produce the product binary

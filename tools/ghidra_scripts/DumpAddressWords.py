#@runtime Jython
# -*- coding: utf-8 -*-
"""Dump 32-bit words at selected program addresses.

Environment:
    AVPE_WORD_TARGETS  Comma-separated ``address[:count]`` values.  ``count``
                       defaults to one word.
"""

import os


targets = os.environ.get("AVPE_WORD_TARGETS", "")
if not targets:
    print("AVPE_WORD_TARGETS not set")
else:
    address_space = currentProgram.getAddressFactory().getDefaultAddressSpace()
    memory = currentProgram.getMemory()

    for raw_target in targets.split(","):
        parts = raw_target.strip().split(":", 1)
        if not parts[0]:
            continue
        start = int(parts[0], 0)
        count = int(parts[1], 0) if len(parts) == 2 else 1
        if count <= 0:
            raise ValueError("word count must be positive: %s" % raw_target)
        for index in range(count):
            address = address_space.getAddress(start + index * 4)
            print("%08x: %08x" % (address.getOffset(), memory.getInt(address) & 0xffffffff))

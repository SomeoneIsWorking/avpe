#@runtime Jython
# -*- coding: utf-8 -*-
"""Find vtable/data entries whose 32-bit value equals a target address.

Scans the program's initialized memory blocks rather than the whole address
range, and names each hit by the owning class symbol when Ghidra has decoded
one. Used to locate a PS2 class vtable from its virtual member addresses.

Environment:
    AVPE_PTR_TARGETS  Comma-separated target addresses (hex) whose pointer
                      occurrences (vtable slots) should be located.
    AVPE_PTR_SPAN     Words to print before/after each hit (default 2).
"""
import os

memory = currentProgram.getMemory()
space = currentProgram.getAddressFactory().getDefaultAddressSpace()
fm = currentProgram.getFunctionManager()
st = currentProgram.getSymbolTable()


def parse(text):
    text = text.strip().lower()
    return int(text[2:], 16) if text.startswith("0x") else int(text, 16)


raw_targets = os.environ.get("AVPE_PTR_TARGETS", "")
if not raw_targets:
    print("AVPE_PTR_TARGETS not set")
else:
    span = parse(os.environ.get("AVPE_PTR_SPAN", "2"))
    wanted = {}
    for raw in raw_targets.split(","):
        if raw.strip():
            wanted[parse(raw)] = raw.strip()

    blocks = memory.getBlocks()
    for block in memory.getBlocks():
        start = block.getStart().getOffset()
        end = block.getEnd().getOffset()
        for addr_offset in range(start, end + 1, 4):
            try:
                word = memory.getInt(space.getAddress(addr_offset)) & 0xffffffff
            except Exception:
                continue
            if word not in wanted:
                continue
            fn = fm.getFunctionAt(space.getAddress(word))
            print("PTR %08x -> %s %s" % (
                addr_offset, wanted[word], fn.getName() if fn else "-"))
            lo = addr_offset - span * 4
            hi = addr_offset + span * 4
            for at in range(lo, hi + 4, 4):
                try:
                    val = memory.getInt(space.getAddress(at)) & 0xffffffff
                except Exception:
                    continue
                mark = " <<<" if at == addr_offset else ""
                tf = fm.getFunctionAt(space.getAddress(val))
                sym = st.getPrimarySymbol(space.getAddress(at))
                sym_name = sym.getName() if sym is not None else ""
                print("    %08x = %08x%-4s %-52s %s" % (
                    at, val, mark, tf.getName() if tf else "", sym_name))

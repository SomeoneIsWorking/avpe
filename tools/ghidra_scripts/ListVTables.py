#@runtime Jython
# -*- coding: utf-8 -*-
"""Dump every ``__vt__`` class vtable's virtual slots with resolved names.

Environment:
    AVPE_VTABLE_SLOTS  Comma-separated slot word offsets to print (default
                       8,12,16,20,24). Slots are byte offsets from the vtable
                       symbol address.
"""
import os

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
memory = currentProgram.getMemory()
fm = currentProgram.getFunctionManager()
st = currentProgram.getSymbolTable()


def parse(text):
    text = text.strip().lower()
    return int(text[2:], 16) if text.startswith("0x") else int(text, 16)


slot_text = os.environ.get("AVPE_VTABLE_SLOTS", "8,12,16,20,24")
slots = [parse(part) for part in slot_text.split(",") if part.strip()]

symbols = st.getAllSymbols(True)
vtables = []
for symbol in symbols:
    name = symbol.getName()
    if not (name.startswith("__vt__") or name.startswith("_vt__")):
        continue
    address = symbol.getAddress()
    try:
        if not memory.contains(address):
            continue
    except Exception:
        continue
    vtables.append((address.getOffset(), name))

vtables.sort()
print("VTABLE COUNT %d" % len(vtables))
for offset, name in vtables:
    row = []
    for slot in slots:
        try:
            word = memory.getInt(space.getAddress(offset + slot)) & 0xffffffff
        except Exception:
            word = 0
        fn = fm.getFunctionAt(space.getAddress(word)) if word else None
        row.append("%02x=%s" % (slot, fn.getName() if fn else "%08x" % word))
    print("%08x %-44s %s" % (offset, name, " | ".join(row)))

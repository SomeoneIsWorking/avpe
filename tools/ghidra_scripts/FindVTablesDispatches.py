#@runtime Jython
# -*- coding: utf-8 -*-
"""Find every vtable dispatch site: a `jalr` whose target register was loaded
from a fixed vtable slot displacement.

AVP:E dispatches a class virtual by loading the slot word out of the vtable into
the same register `jalr` then calls, so a short forward window over
`lw <reg>, <disp>(<reg>)` followed by `jalr <reg>` identifies the dispatch.

Environment:
    AVPE_DISP_SLOTS   Comma-separated vtable slot displacements to match
                      (default 24 for the 0x18 render slot).
    AVPE_DISP_WINDOW  Instructions to look ahead for the `jalr` (default 3).
"""
import os

space = currentProgram.getAddressFactory().getDefaultAddressSpace()
listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()


def parse(text):
    text = text.strip().lower()
    return int(text[2:], 16) if text.startswith("0x") else int(text, 16)


slots = [parse(part) for part in os.environ.get("AVPE_DISP_SLOTS", "24").split(",") if part.strip()]
window = parse(os.environ.get("AVPE_DISP_WINDOW", "3"))

hits = 0
for instruction in listing.getInstructions(True):
    mnemonic = instruction.getMnemonicString()
    if mnemonic != "lw":
        continue
    raw = str(instruction.toString())
    parts = raw.split(",", 1)
    if len(parts) != 2:
        continue
    operand = parts[1].strip()
    if "(" not in operand:
        continue
    displacement_text = operand.split("(", 1)[0].strip()
    if not displacement_text:
        continue
    if displacement_text.lower().startswith("-"):
        try:
            displacement_value = -parse(displacement_text[1:])
        except ValueError:
            continue
    else:
        try:
            displacement_value = parse(displacement_text)
        except ValueError:
            continue
    if displacement_value not in slots:
        continue
    destination = parts[0].split()[-1]
    # Walk forward looking for `jalr <destination>` (or a moved copy).
    it = listing.getInstructions(instruction.getMaxAddress().next(), True)
    seen = 0
    forward = []
    while it.hasNext() and seen < window:
        ahead = it.next()
        seen += 1
        forward.append(ahead)
        ahead_text = str(ahead.toString())
        if ahead_text.startswith("jalr") or ahead_text.startswith("jr "):
            operand_text = ahead_text.split(None, 1)[1] if " " in ahead_text else ""
            if operand_text == destination:
                fn = fm.getFunctionContaining(instruction.getAddress())
                fname = fn.getName() if fn else "<no-fn>"
                fstart = fn.getEntryPoint() if fn else instruction.getAddress()
                print("DISP slot=%#x at %s in %s @ %s :: %s" % (
                    displacement_value, instruction.getAddress(), fname, fstart, ahead_text))
                hits += 1
                break
print("TOTAL %d dispatch sites" % hits)

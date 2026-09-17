#@runtime Jython
# -*- coding: utf-8 -*-
"""Dump per-instruction disassembly (address, mnemonic, operands) for one
function, identified by any vaddr inside it.  Used to pin an exact
post-call instruction address that C decompilation output cannot show.

Env vars:
    DISASM_TARGET   hex/dec vaddr inside the target function (required)
    DISASM_OUT      output dir (default ./build/decomp)
"""

import os

OUT = os.environ.get("DISASM_OUT", os.path.join(os.getcwd(), "build", "decomp"))
if not os.path.isdir(OUT):
    os.makedirs(OUT)

target = os.environ.get("DISASM_TARGET", "")
if not target:
    print("DISASM_TARGET not set")
else:
    af = currentProgram.getAddressFactory().getDefaultAddressSpace()
    fm = currentProgram.getFunctionManager()
    listing = currentProgram.getListing()

    addr = af.getAddress(int(target, 0))
    fn = fm.getFunctionContaining(addr)
    if fn is None:
        print("no function contains %s" % target)
    else:
        body = fn.getBody()
        out_path = os.path.join(OUT, "%s.disasm.txt" % fn.getEntryPoint())
        with open(out_path, "w") as f:
            f.write("function %s @ %s\n" % (fn.getName(), fn.getEntryPoint()))
            it = listing.getInstructions(body, True)
            while it.hasNext():
                ins = it.next()
                line = "%s: %s" % (ins.getAddress(), ins.toString())
                f.write(line + "\n")
                print(line)
        print("WROTE %s" % out_path)

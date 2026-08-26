#@runtime Jython
# List every function that calls the target VA (Reference DB call xrefs).
# Env: AVPE_CALL_TARGET=<hex vaddr>
import os
from ghidra.program.model.symbol import RefType

target = os.environ.get("AVPE_CALL_TARGET")
if not target:
    print("AVPE_CALL_TARGET not set")
else:
    af = currentProgram.getAddressFactory().getDefaultAddressSpace()
    fm = currentProgram.getFunctionManager()
    rm = currentProgram.getReferenceManager()
    addr = af.getAddress(target)
    n = 0
    for ref in rm.getReferencesTo(addr):
        if ref.getReferenceType() in (RefType.COMPUTED_CALL, RefType.UNCONDITIONAL_CALL):
            frm = ref.getFromAddress()
            fn = fm.getFunctionContaining(frm)
            name = fn.getName() if fn else "<no-fn>"
            print("CALLER %s from %s (%s)" % (frm, name, fn.getEntryPoint() if fn else "-"))
            n += 1
    if n == 0:
        print("scanned references to %s: 0 call-type refs (fn-ptr dispatch or DB miss)" % target)

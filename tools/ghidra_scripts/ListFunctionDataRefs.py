#@runtime Jython
# -*- coding: utf-8 -*-
"""List non-call references and decoded data for selected functions.

Environment:
    AVPE_FN_TARGETS  Comma-separated function addresses.
"""

import os


targets = os.environ.get("AVPE_FN_TARGETS", "")
if not targets:
    print("AVPE_FN_TARGETS not set")
else:
    address_space = currentProgram.getAddressFactory().getDefaultAddressSpace()
    functions = currentProgram.getFunctionManager()
    listing = currentProgram.getListing()
    references = currentProgram.getReferenceManager()

    for raw_target in targets.split(","):
        target = raw_target.strip()
        if not target:
            continue
        function = functions.getFunctionContaining(address_space.getAddress(target))
        if function is None:
            print("FUNCTION %s <not found>" % target)
            continue

        print("FUNCTION %s %s" % (function.getEntryPoint(), function.getName()))
        instructions = listing.getInstructions(function.getBody(), True)
        while instructions.hasNext():
            instruction = instructions.next()
            for reference in references.getReferencesFrom(instruction.getAddress()):
                if reference.getReferenceType().isCall():
                    continue
                destination = reference.getToAddress()
                symbol = currentProgram.getSymbolTable().getPrimarySymbol(destination)
                data = listing.getDataContaining(destination)
                value = ""
                if data is not None:
                    rendered = data.getDefaultValueRepresentation()
                    if rendered is not None:
                        value = " value=%s" % rendered
                print("  %s -> %s type=%s symbol=%s%s" % (
                    instruction.getAddress(),
                    destination,
                    reference.getReferenceType(),
                    symbol.getName() if symbol is not None else "-",
                    value,
                ))

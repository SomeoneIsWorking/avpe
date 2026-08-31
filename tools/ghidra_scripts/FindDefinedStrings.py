#@runtime Jython
# -*- coding: utf-8 -*-
"""Find defined string data whose rendered value contains a query.

Environment:
    AVPE_STRING_QUERY  Case-insensitive text to find (required).
    AVPE_STRING_LIMIT  Maximum matches to print (default 100).
"""

import os


query = os.environ.get("AVPE_STRING_QUERY", "").lower()
if not query:
    print("AVPE_STRING_QUERY not set")
else:
    limit = int(os.environ.get("AVPE_STRING_LIMIT", "100"), 0)
    if limit <= 0:
        raise ValueError("AVPE_STRING_LIMIT must be positive")

    listing = currentProgram.getListing()
    symbols = currentProgram.getSymbolTable()
    scanned = 0
    matched = 0
    shown = 0
    data_iter = listing.getDefinedData(True)
    while data_iter.hasNext():
        data = data_iter.next()
        rendered = data.getDefaultValueRepresentation()
        if rendered is None:
            continue
        scanned += 1
        if query not in rendered.lower():
            continue
        matched += 1
        if shown >= limit:
            continue
        address = data.getAddress()
        symbol = symbols.getPrimarySymbol(address)
        print("STRING %s symbol=%s value=%s" % (
            address,
            symbol.getName() if symbol is not None else "-",
            rendered,
        ))
        shown += 1
    print("SCANNED %d defined data items; MATCHED %d; SHOWN %d" %
          (scanned, matched, shown))

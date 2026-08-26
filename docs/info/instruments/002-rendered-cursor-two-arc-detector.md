---
id: I002
kind: instrument
status: trusted
created: 2026-08-26
---

## Instrument

`avpe.cursor.detect_cursor` identifies AVP:E's rendered pointer from the paired
gold arc components in an uncompressed 24-bit `/snap` BMP near an expected
screen target.

## Validated by

The production detector accepted a synthetic BMP containing the required two
separate arc-like components and rejected the same color mask with only one
component. It also rejected malformed BMP bytes. Against prior real mission
snapshots it detected the cursor at approximately `(320.4,232.0)` in three
known cursor frames and returned no cursor for the deliberately differing
`b.bmp` frame. The C009 run then produced distinct positive detections at both
injected targets.

## Known failure modes

The color and component geometry are specific to AVP:E's current pointer art
and 24-bit control snapshots. A palette, post-processing, resolution-scaling,
or cursor-art change must be revalidated with a frame that contains the cursor
and one that does not. Search is intentionally constrained near the requested
target so similarly colored HUD elements do not qualify.

---
id: 16
title: Ground title-observed native asset failure semantics
status: open
symptom: Success bytes and store-admission failures are grounded, but the title's observable short-read and transient read-error recovery paths are not traced end to end
state_items: S024
tags: assets,errors,equivalence,re
created: 2026-08-28
updated: 2026-08-28
---

## Scope

Trace only failure and short-read outcomes the supported title can actually
observe after a native claim, including its ordered read, `sceCdGetError`,
reopen, reseek, and retry behavior. Do not require exhaustive reproduction of
malformed-disc or optical-media behavior that is outside G005.

## Acceptance

- Each claimed guest-visible failure semantic has an exact original-path
  post-return observer.
- Native fault injection reproduces the ordered title-visible result and final
  buffer effect.
- Missing or invalid stores still fail before a native claim and never silently
  fall back.

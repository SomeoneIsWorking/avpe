# Prior art

External work on Aliens Versus Predator: Extinction (PS2, `SLUS_201.47`, PCSX2 CRC `64DA78A3`). The retail ELF keeps its `.symtab` (~15k symbols), which remains the primary name source. Addresses were checked against the provisioned `SLUS_201.47` (LOAD `0x00100000`, file offset `0x80`) and its symbols.

| project | URL | kind | license | target build | build match (addresses checked) | what we may take | notes |
|---|---|---|---|---|---|---|---|
| PCSX2 patches, `SLUS-20147_64DA78A3.pnach` | https://github.com/PCSX2/pcsx2_patches | PCSX2 widescreen and 60 FPS patches | none (no LICENSE file) | NTSC-U `SLUS-20147`, CRC `64DA78A3` | matched: CRC equals our PCSX2 `/status`; `0x0017FC74` holds `lui v0,0x3F80` inside `CMatrix::LookAt` (patch writes `0x3F40`); `0x00179110` holds `0x4501FFF1` inside `CRendAPI::EndFrame`, the original word the pnach itself records | evidence only | Widescreen changes a LookAt aspect constant; 60 FPS flips a branch in `EndFrame` and notes it may need EE overclock. |
| AVP2-Reconstructed | https://github.com/lemiur/AVP2-Reconstructed | PC decompilation of Aliens vs. Predator 2 | none | PC AvP2 (different game) | n/a | nothing | Listed on decomp.dev; unrelated engine. |

Not found (searched 2026-10-13): an AVP:E decompilation, recompilation, native port, symbol map or Ghidra/IDA database (GitHub, decomp.dev, recompiled-games lists), modding SDKs or RE wikis for the PS2 or Xbox release.

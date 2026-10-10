# 0022 PS2 surface inventory

Every user-facing screen and HUD element in `SLUS_201.47` (its `ClassId__` symbols), with what
the port has changed. Most of the game is still the PS2 game: list menus moved by d-pad focus, pad
button glyphs in text, and a 4:3 TV layout. Key caps over glyph meshes (S029) and the mission
mouse work (issue 0021) are the only PC-native layers, and both were checked only in the Marine
campaign's first mission and the profile and pause menus.

`pc` — works as a PC game. `caps` — PS2 navigation with key caps over glyph meshes and keys
mapped to pad buttons. `ps2` — unchanged. `unseen` — never reached under the port.

## Front end

| class | screen | state |
|---|---|---|
| `GPressStartMenu` | title | caps: Enter named and works |
| `GMainMenu`, `GStartMenu` | main menu | caps: list focus, no hover or click proof |
| `GCampaignMenu` | species and mission select | unseen |
| `GProfileMenu`, `GNewProfileMenu`, `GLoadProfileMenu`, `GDeleteProfileMenu` | profiles | caps: Enter/Esc seen; typing a name (`GMenuEditBox`) unchecked |
| `GSaveGameMenu`, `GLoadGameMenu`, `GLSDeleteMenu`, `GOverwriteMenu`, `GSaveOverwriteOrNewProfileMenu`, `GEndGameSaveProfileMenu`, `GLoadConfirmationMenu` | save and load | ps2: memory-card slot model (S016) |
| `GFormatPacifyMenu`, `GFormatYesMenuButton`, `GNoSpaceForProfileMenu`, `GSaveFailedMenu`, `GErrorDeletingProfileMenu`, `*PacifyMenu` | memory-card format, space and progress dialogs | ps2: must become unreachable (S016) |
| `GGoToDashboardConfirmMenu` | console dashboard exit | unseen; has no PC meaning |
| `GControlOptionsMenu` | controls | ps2: pad layout, no key bindings (S029) |
| `GAudioOptionsMenu` | audio | caps: mouse clicks on its buttons work |
| no class | graphics, display, resolution | missing (S018) |
| `GCheatsMenu`, `GCreditsMenu`, `GBeastiaryMenu`, `GMatrixModeMenu` | extras | unseen |
| `GLoadingScreen`, `GLevelLoadErrorMenu`, `GPressKeyToContinueMenu` | loading | caps: load error names Enter |
| `GMultiplayerSynchronizingMenu` | multiplayer sync | unseen |

## Mission

| class | element | state |
|---|---|---|
| `GAvPPointer`, `GMarinePointer` | selection, right-click, edge scroll, minimap | pc for Marines (issue 0021); selection still drawn as a disk |
| `GMarineUI` | Marine unit menu (d-pad items, R1 special) | caps: order letters, groups, Space/Backspace, Q; items not clickable |
| `GAlienUI`, `GPredatorUI` | Alien and Predator unit menus | unseen: no key or mouse path checked |
| `GCommandListMenu`, `GToggleMenuButton` | order card | caps: shown only while Tab is held, not clickable |
| `GOrderingMenu`, `GOrderingIconDisplay`, `GMiscCostDisplay`, `GUnitCapDisplay` | Marine Dropship Uplink (buy units) | caps: opens only with Q on one Comm Tech; PS2 navigation, items not clickable |
| `GAlienUpgradeMenu`, `GConfirmUpgradeMenu` | Alien morph and upgrade | unseen |
| Predator honour and skull spending (`GStatSkullsDisplay`, `GStatSkullKeeperEnergyDisplay`) | Predator economy | unseen |
| `GInGameStatMenu`, `GStatSubMenu`, `GStat*Display` | unit status panel | pc: follows pointer or first selected unit |
| `GInGameMenu`, `GMenuBarIndicator`, `GScreenDecor` | HUD frame | ps2: the PS2 HUD layout; widescreen unchecked |
| `GScrollingTextDisplay` | tutorial and mission text | ps2: inline font glyphs name pad buttons |
| `GMissionGoalsMenu`, `GMissionGoalsScreen` | objectives | unseen under PC keys |
| `GPauseMenu`, `GRestartConfirmMenu` | pause | caps: navigation and keys verified in M1 |
| `GMissionEndMenu` | debrief | unseen |
| `GTimeLimitDisplayButton` | timer | unseen |

## Next

Reach the Alien and Predator campaigns and the unseen screens, then convert each surface,
starting with the in-mission command surfaces (order card, Dropship Uplink, Alien and Predator
equivalents) as clickable panels.

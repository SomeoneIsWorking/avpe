---
id: C018
kind: claim
status: holds
created: 2026-08-27
tags: assets,provisioning,validation
depends: src/avpe/native_assets.py#provision_native_assets, src/avpe/iso9660.py#IsoImage, src/avpe/raw_sector.py#strip_image
---

## Claim

The supported AVP:E CHD can be provisioned into a complete versioned native store whose 137 files are validated by exact path, size, and SHA-256 before atomic publication

## Evidence

The 2026-08-27 real-disc provision converted 268924 MODE2 Form1 sectors, validated SYSTEM.CNF, SLUS_201.47, and TBD/TBF.TBF anchors, extracted 137 files totaling 550353354 bytes, hashed every file, published avpe-native-assets-v1 with no staging remainder, and a second run fully revalidated it; production negative tests reject another ISO identity, wrong manifest identity, and missing files

## What would falsify it

a clean provision of the supported user CHD produces bytes that differ from its manifest or original file extents, publishes a partial store after failure, accepts a wrong/corrupt identity, or cannot be revalidated

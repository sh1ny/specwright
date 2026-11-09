# 0032. Third-party notices accompany sw

- Status: accepted
- Date: 2026-11-09
- Adds to: 0027

## Context

The approved HTML parser brings direct and transitive runtime dependencies into the standalone executable. Binary redistribution requires their copyright, permission and disclaimer notices, and the embedded Dart runtime has its own licence. The user chose a notice file beside the binary.

## Decision

From version 0.30.0, every platform artifact contains byte-identical `THIRD_PARTY_NOTICES.txt` from `cli/THIRD_PARTY_NOTICES.txt` and its SHA-256 sidecar. The source uses LF checkouts. A numeric version comparison gates packaging; older tags require no notice. The five binary names stay unchanged. Release attachment reads back all six required assets before uploading the sorted `SHA256SUMS` seal last. Sealed releases are immutable, including an incomplete new-format release.

Release installation verifies both hashes before quarantine removal or executing the downloaded binary. After the binary passes its version and interface checks, the installer places the notice before keeping or replacing the binary. A matching notice is untouched. A failed notice rename succeeds only if another installer placed the expected bytes; otherwise installation stops without replacing the binary. Owned notice parts follow the existing cleanup and download bounds. A crash after notice placement is recoverable on rerun.

Source installation checks the build, places the tree notice, renames the binary and performs the final resolver check. No notice command is added.

**C14:** From 0.30.0, the checksummed third-party notice accompanies the binary in release artifacts and installs; it is verified before executing a downloaded binary, and older release manifests remain usable. A change to the compiled dependency set updates the notice.

## Consequences

The installed version directory and release assets contain one additional text file. The notice records every direct and transitive compiled package and applicable embedded-runtime notices. Dependency changes must update it; checksum verification alone cannot detect stale attribution. ADR 0027 remains unchanged.

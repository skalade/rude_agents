# Credential audit before publication

The exact indexed publication tree and all 26 reachable commits were checked
locally with Gitleaks 8.30.1 and its default rules, recursive decoding enabled.
No rules, directories or findings were suppressed. Known locally configured
credentials were also compared against the index and historical blobs without
recording their values in the report.

No configured credentials matched. The historical scan reported no findings.
The initial indexed-tree scan reported 22 findings. Twelve were case-normalized
copies of a `FAKE_HUGGINGFACE_TOKEN_2` fixture in verifier failures; the other ten
were password-recovery challenge answers, guesses or binary-data fragments
mistaken for API keys by the generic detector.

Credential-shaped `FAKE_*` examples from `sanitize-git-repo` have been masked in
the exported logs, including a documented fake AWS secret example. Masks retain
string lengths and trace line numbers. The result and test-status fields are
unchanged, and artifact hashes have been updated. The fixed password from the
password-recovery task and the agents' guesses remain benchmark data.

Fixture provenance:

- `terminal-bench-2/sanitize-git-repo/tests/test_outputs.py`: named `FAKE_*` constants.
- `terminal-bench-2/password-recovery/environment/setup.sh`: fixed challenge password.
- `terminal-bench-2/password-recovery/tests/test_outputs.py`: expected challenge answer.

The `.envrc` file, authentication files, local caches, full model logs and personal
Claude session are not part of the Git publication tree. Only the shutdown quote
already used in the post is included. Git author metadata, local path names and
provider generation IDs remain ordinary provenance metadata, not access credentials.

This records checks on this publication snapshot, not credential validation
against third-party services. No candidate key was sent to an external service.

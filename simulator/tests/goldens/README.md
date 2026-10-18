# Approved simulator goldens

This directory contains only independently reviewed baselines. It is currently
empty: Plan 10 never promotes generated render output to a trusted reference.

A baseline consists of `<scene>.rgb565` (row-major, little-endian RGB565) and
`<scene>.json`. The sidecar must declare schema version 1, `status: APPROVED`,
scene id, dimensions, profile hash, source revision, SHA-256 of the baseline,
approver, and approval reason. The CLI manifest uses a `golden_approval` object
with `status`, `approved_by`, and `approval_reason`; attach it only after the
expected frame has been independently verified. Approval requires comparison
with an independent oracle or separately reviewed physical reference. A
simulator run cannot approve or update a golden. There is deliberately no
golden-update CLI.

`compare_golden` returns `NO_BASELINE` when neither file exists, `INCONCLUSIVE`
for missing, malformed, unapproved, checksum-invalid, or profile-incompatible
references, and `FAIL` for any changed RGB565 pixel. Newly generated snapshots
remain under the caller's output directory.

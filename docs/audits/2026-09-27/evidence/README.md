# Audit evidence

Target: repository commit `310e50cfe9b8087c8a2af64e6e74f098548e6824`.

* `baseline-0.txt`: workspace validation command, exit and output.
* `baseline-1.txt`: all 193 unittest names and results.
* `baseline-2.txt`: 28 regression results and fingerprint.
* `baseline-3.txt`: critic corpus; seven deterministic cases scored and two live cases missing.
* `final-0.txt` through `final-3.txt`: the same checks rerun after writing the audit and registering sources; all exit zero.
* `repository-manifest.json`: SHA-256 and size for 544 tracked files before audit deliverables/source-registration changes; Python version and initial untracked directories.
* `candidate-status.json`: gate status for all 46 candidate files in six non-template projects. Readiness is the present gate's answer, not a claim of literary quality or authenticated historical review.
* `probes.py`: isolated audit reproductions using the current library and disposable projects. No network or paid inference. This is evidence code, not an addition to the production test suite.
* `probe-results.json`: 24 observations from that script. Most demonstrate defects; they are not 24 newly passing quality checks.
* `research-sources.json`: the 32 references added to the source register, including access depth and transfer limitations.

From the repository root, rerun:

```sh
python3 docs/audits/2026-09-27/evidence/probes.py
```

The script overwrites only its sibling `probe-results.json`; all simulated promotion and mutation work occurs in a temporary directory that is removed on exit. Compare observations with this audit; the script does not assert desired fixed behavior. Once repairs are authorized, convert relevant cases into maintained regression tests with expected safe outcomes.

The race probe inserts one promotion immediately before the other acquires its lock. It demonstrates an allowed stale-read interleaving; it is not a high-volume parallel stress test. Vendor mutation uses an offline responder that edits the candidate after packet construction. No actual API credentials were read for these probes.

No external LLM judge, separate human reviewer or live provider compatibility test was used. The review was double-checked by combining source inspection, direct reproduction, existing tests, research cross-checks and explicit counterarguments.

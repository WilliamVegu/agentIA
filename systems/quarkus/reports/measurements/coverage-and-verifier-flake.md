# Verification-guided selection, measured on agentIA — and the verifier flake

**Date:** 2026-09-29
**One hour, zero API spend.** Every number here comes from data already collected
(`instruction-polarity.json`) and free sandbox rebuilds.

---

## 1. The result: coverage scaling is real and cheap here

The control arm of the polarity experiment is 6 tasks, each resampled 3–4 times with
the same instructions and model — exactly the setup *Large Language Monkeys*
(arXiv:2407.21787) uses to measure `coverage(k) = 1 − (1 − p)^k`.

| Metric | Value |
|---|---|
| pass@1 (single sample) | **78.3%** |
| coverage(k=1) | 83.3% |
| coverage(k=2) | 83.3% |
| **coverage(k=3)** | **100%** |
| coverage(k=4) | 100% |

Read: a single generated service builds **78%** of the time; generating **3** and
keeping the first one that builds raises task-level reliability to **6/6**. At
$0.065/task that is **$0.20 per reliable service**.

**Caveats, stated not smoothed:** n = 6 tasks (two tasks have only 3 samples, so the
k=4 cell reuses the third), one model, one provider. This is a *demonstration of the
lever*, not a benchmark. The direction is robust — coverage is monotone in k by
construction — but the 100% is "6 of 6 tasks", not a rate to publish.

## 2. The blocker: the verifier is *intermittently* flaky

The same frozen workspace, rebuilt under load earlier, gave **4 pass / 2 fail**.
Rebuilt sequentially just now, two workspaces give **8/8 and 8/8**. The failure
signature, when it occurs, is a `surefire` `PluginContainerException` on a
`surefire-shared-utils` foreign import — **after every test has passed**.

The flake is therefore **not a per-workspace code defect**. It is intermittent and
load-correlated. The leading hypothesis is the mount configuration:

* `backend/.env` sets `DOCKER_MOUNT_SUFFIX=:Z`.
* `:Z` is a **private** SELinux relabel — correct for a workspace private to one
  session, **wrong for a shared read-only Maven cache mounted by many concurrent
  containers**. Two containers relabelling the same shared source with `:Z` is a
  known cause of exactly this class of intermittent class-realm/resolution failure.
* The same suffix is applied to both mounts, so the private and shared mounts are
  conflated.

**Proposed fix (untested):** apply `:Z` to the workspace mount and **no relabel** (or
`:z`, shared) to the read-only Maven cache. This is a one-line change to
`mount_spec`'s call sites and needs the repeatability gate below to confirm.

## 3. What "done" looks like

1. Split the mount suffix: workspace `:Z`, cache unrelabelled (or `:z`).
2. A **repeatability gate**: rebuild one frozen workspace N times; it must pass
   N/N before any build-rate or coverage number is trusted.
3. Re-measure pass@1 and coverage on a stable verifier — then the numbers in §1 stop
   being a demonstration and become a claim.

## 4. The decision this enables

With a stable verifier, **verification-guided selection is the product's reliability
mechanism**, and it needs nothing the platform does not already have: a free
deterministic build, a free platform contract test, and ~$0.20 per reliable service.
This is the lever the literature ranks first, and it is now measured on agentIA
rather than borrowed from another task class. The skill-optimisation loop, by
contrast, stays gated behind the verifier fix — which is the same gate, one level
down.

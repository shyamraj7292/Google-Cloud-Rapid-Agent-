# Few-Shot Examples for Copa Agent

## Example 1: Pipeline Triage

**User**: The ticketing API pipeline is failing. Can you check?

**Agent**: 
Let me investigate the ticketing API pipeline right away. ⚡

*[Calls list_pipelines for worldcup-ticketing-api]*

I found the issue — Pipeline #42 has status `failed`. Let me dig into the failing job.

*[Calls list_pipeline_jobs for pipeline #42]*

The `unit_test` job failed. Let me read the logs.

*[Calls get_pipeline_job_log for the failing job]*

**Root Cause Found** ❌: The unit test `test_auth_token_validation` in `tests/test_auth.py` is failing with:
```
AssertionError: Expected token expiry 3600, got 360
```

It looks like someone changed the `TOKEN_EXPIRY_SECONDS` constant from `3600` to `360` — likely a typo (missing a zero). 

Want me to create a fix branch and merge request to correct this?

**User**: Yes, fix it.

**Agent**:
On it! ⚡

*[Calls create_branch: "fix/auth-token-expiry" from "main"]*
*[Calls create_or_update_file: fixes TOKEN_EXPIRY_SECONDS to 3600]*
*[Calls create_merge_request: title "Fix: Auth token expiry typo (360→3600)"]*

Done! ✅ I've created:
- Branch: `fix/auth-token-expiry`
- MR #17: "Fix: Auth token expiry typo (360→3600)"

The pipeline is now running on the fix branch. Once it passes, you can merge it. Want me to monitor it and auto-merge when green?

---

## Example 2: Cross-Repo Status Check

**User**: What's the status of all our World Cup pipelines?

**Agent**:
Let me check all services for you. ⚡

*[Calls list_pipelines for each repo]*

Here's your World Cup Platform Status Report:

| Service | Latest Pipeline | Status | Branch |
|---------|----------------|--------|--------|
| worldcup-fan-app | #78 | ✅ Passed | main |
| worldcup-ticketing-api | #42 | ❌ Failed | main |
| worldcup-stadium-dashboard | #31 | 🔄 Running | main |

**Summary**: 1 service healthy, 1 failing (ticketing-api), 1 in progress (stadium-dashboard).

The ticketing-api failure is the auth token issue we discussed. Want me to triage the stadium-dashboard pipeline or wait for it to complete?

---

## Example 3: Issue to Merge Request

**User**: We need to add Spanish language support to the fan app. Can you create an issue and start working on it?

**Agent**:
Great idea — with venues in Mexico, Spanish support is essential! Let me set that up. ⚡

*[Calls create_issue: title "feat: Add Spanish (es) language support", body with i18n requirements]*

Issue #23 created ✅. Now let me start the implementation.

*[Calls create_branch: "feature/spanish-i18n" from "main"]*
*[Calls create_or_update_file: creates src/i18n/es.json with Spanish translations]*
*[Calls create_or_update_file: updates src/i18n/index.js to register Spanish locale]*
*[Calls create_merge_request: title "feat: Add Spanish language support", linked to issue #23]*

All set! ✅ Here's what I created:
- **Issue #23**: "feat: Add Spanish (es) language support"
- **Branch**: `feature/spanish-i18n`
- **MR #18**: "feat: Add Spanish language support" (linked to Issue #23)

The MR includes initial translation files for key UI strings. Your team will want to review the translations and add any missing strings. ⚽

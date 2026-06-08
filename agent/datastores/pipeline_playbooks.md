# CI/CD Pipeline Troubleshooting Playbooks

## Common Failure Patterns

### 1. Unit Test Failures
**Symptoms**: Pipeline fails at `test` stage, job log shows `AssertionError` or `FAILED`
**Root Causes**:
- Code logic bug in recent commit
- Missing test fixture or mock data
- Environment variable not set in CI
- Dependency version mismatch

**Resolution Steps**:
1. Read the job log to identify the failing test file and line number
2. Get the file contents from the repository
3. Identify the bug (often a typo, wrong constant, or missing edge case)
4. Create a fix branch and push the correction
5. Open a merge request with the fix

### 2. Build/Compile Failures
**Symptoms**: Pipeline fails at `build` stage, log shows syntax errors or import failures
**Root Causes**:
- Syntax error in recent commit
- Missing dependency in requirements.txt or package.json
- Incompatible dependency versions
- Missing environment variable at build time

**Resolution Steps**:
1. Check the build log for the specific error message
2. If dependency issue: update requirements.txt/package.json
3. If syntax error: fix the code directly
4. If env var missing: add it to .gitlab-ci.yml variables section

### 3. Lint/Style Failures
**Symptoms**: Pipeline fails at `lint` stage, shows formatting or style violations
**Root Causes**:
- Code doesn't match project style guide (flake8, eslint, prettier)
- Trailing whitespace, unused imports, missing docstrings

**Resolution Steps**:
1. Read the lint output to see which rules are violated
2. Auto-fix where possible (run formatter)
3. Manual fix for logic-based lint errors
4. Update .flake8 or .eslintrc if rule should be relaxed

### 4. Docker Build Failures
**Symptoms**: Pipeline fails at `docker_build` stage
**Root Causes**:
- Dockerfile syntax error
- Base image not available
- COPY command references non-existent file
- Multi-stage build intermediate stage failed

**Resolution Steps**:
1. Check which Dockerfile instruction failed
2. Verify file paths match repository structure
3. Check if base image tag still exists on Docker Hub
4. Fix Dockerfile and push update

### 5. Deploy Failures
**Symptoms**: Pipeline passes build/test but fails at `deploy` stage
**Root Causes**:
- Cloud Run quota exceeded
- IAM permissions insufficient
- Health check failing on new container
- Port mismatch (container listens on wrong port)

**Resolution Steps**:
1. Check deploy log for specific GCP error
2. Verify service account permissions
3. Check if health check endpoint is responding
4. Verify PORT environment variable matches Dockerfile EXPOSE

### 6. Security Scan Failures (SAST/DAST)
**Symptoms**: Pipeline fails at `security_scan` stage
**Root Causes**:
- Hardcoded secrets in code
- Known vulnerable dependency version
- SQL injection or XSS vulnerability detected

**Resolution Steps**:
1. Read security scan report
2. Prioritize by severity (Critical → High → Medium)
3. For hardcoded secrets: move to environment variables
4. For vulnerable dependencies: upgrade to patched version
5. For code vulnerabilities: apply recommended fix pattern
6. Create issue for each finding with `security` label

---

## Pipeline Configuration Reference

### Standard .gitlab-ci.yml Structure
```yaml
stages:
  - build
  - test
  - lint
  - security_scan
  - deploy

variables:
  PYTHON_VERSION: "3.11"
  NODE_VERSION: "20"

build:
  stage: build
  script:
    - pip install -r requirements.txt
  artifacts:
    paths:
      - venv/

test:
  stage: test
  script:
    - pytest tests/ -v
  coverage: '/TOTAL.*\s+(\d+%)$/'

lint:
  stage: lint
  script:
    - flake8 app/
  allow_failure: true

deploy:
  stage: deploy
  script:
    - gcloud run deploy $SERVICE_NAME --source .
  only:
    - main
  when: manual
```

---

## Quick Reference: GitLab CI Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `CI_COMMIT_SHA` | Full commit hash | `abc123def456` |
| `CI_COMMIT_REF_NAME` | Branch or tag name | `main`, `fix/auth` |
| `CI_PIPELINE_ID` | Pipeline number | `42` |
| `CI_PROJECT_PATH` | Full project path | `worldcup/fan-app` |
| `CI_MERGE_REQUEST_IID` | MR number | `17` |

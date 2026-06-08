"""
Copa Agent — backend tests
===========================

These lock in the behaviors the demo depends on, all in SIMULATION mode (no live
GitLab/LLM needed), so CI stays green and judges can reproduce in one command:

    cd backend && pytest tests/ -v
"""

import os
import sys
import asyncio

import pytest

# Make `services` importable when run from repo root or backend/.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.gitlab_tools import GitLabToolExecutor          # noqa: E402
from services.grounding_service import GroundingService        # noqa: E402
from services.agent_service import AgentService                # noqa: E402


# ---------------------------------------------------------------------------
#  GitLab tool executor (simulation)
# ---------------------------------------------------------------------------
def test_executor_starts_in_simulation_without_token(monkeypatch):
    monkeypatch.delenv("GITLAB_PERSONAL_ACCESS_TOKEN", raising=False)
    ex = GitLabToolExecutor()
    assert ex.mode == "simulation"


def test_ticketing_pipeline_starts_failed():
    ex = GitLabToolExecutor()
    res = ex.list_pipelines("worldcup-ticketing-api")
    assert res["ok"]
    assert any(p["status"] == "failed" for p in res["pipelines"])


def test_failing_job_log_contains_root_cause():
    ex = GitLabToolExecutor()
    res = ex.get_pipeline_job_log("worldcup-ticketing-api", "unit_test", 42)
    assert res["ok"]
    assert "AssertionError" in res["log"]
    assert "3600" in res["log"] and "360" in res["log"]


def test_fix_then_rerun_turns_pipeline_green():
    """The headline moment: applying the real fix makes the pipeline pass."""
    ex = GitLabToolExecutor()
    branch = "fix/auth-token-expiry"
    assert ex.create_branch("worldcup-ticketing-api", branch)["ok"]

    original = ex.get_file_contents("worldcup-ticketing-api", "app/main.py")["content"]
    fixed = original.replace("TOKEN_EXPIRY_SECONDS = 360", "TOKEN_EXPIRY_SECONDS = 3600")
    assert "TOKEN_EXPIRY_SECONDS = 3600" in fixed

    commit = ex.create_or_update_file(
        "worldcup-ticketing-api", "app/main.py", fixed, branch, "fix expiry")
    assert commit["ok"]

    run = ex.run_pipeline("worldcup-ticketing-api", branch)
    assert run["ok"]
    assert run["status"] == "success", "fixed branch must pass the pipeline"


def test_unfixed_branch_still_fails():
    """Negative control: a branch without the fix must NOT go green."""
    ex = GitLabToolExecutor()
    ex.create_branch("worldcup-ticketing-api", "chore/noop")
    run = ex.run_pipeline("worldcup-ticketing-api", "chore/noop")
    assert run["status"] == "failed"


def test_create_merge_request_returns_iid_and_url():
    ex = GitLabToolExecutor()
    res = ex.create_merge_request(
        "worldcup-ticketing-api", "fix/x", "fix: thing", "desc")
    assert res["ok"]
    assert isinstance(res["mr_iid"], int)
    assert res["web_url"].startswith("https://")


def test_unknown_project_errors_cleanly():
    ex = GitLabToolExecutor()
    res = ex.list_pipelines("does-not-exist")
    assert res["ok"] is False
    assert "error" in res


# ---------------------------------------------------------------------------
#  Grounding
# ---------------------------------------------------------------------------
def test_grounding_indexes_local_runbooks():
    g = GroundingService()
    assert g.mode in ("local", "vertex")
    assert len(g._sections) > 0


def test_grounding_finds_unit_test_playbook():
    g = GroundingService()
    res = g.search("unit test AssertionError failing pipeline")
    assert res["ok"]
    assert res["citations"], "should return at least one citation"
    top = res["citations"][0]
    assert "Unit Test" in top["section"] or "test" in top["snippet"].lower()


# ---------------------------------------------------------------------------
#  Agent scripted loop (full workflow)
# ---------------------------------------------------------------------------
def _collect(agent, message, session="t"):
    async def run():
        actions, reply = [], ""
        async for ev in agent.run_stream(message, session):
            if ev["type"] == "action":
                actions.append(ev)
            elif ev["type"] == "reply":
                reply = ev["reply"]
        return actions, reply
    return asyncio.run(run())


def test_scripted_triage_runs_full_workflow():
    agent = AgentService()
    assert agent.mode == "scripted"  # no LLM in test env
    actions, reply = _collect(agent, "the ticketing pipeline is failing, fix it")

    tools_used = [a["tool"] for a in actions]
    for expected in ("list_pipelines", "get_pipeline_job_log", "search_runbooks",
                     "create_branch", "create_or_update_file",
                     "create_merge_request", "run_pipeline"):
        assert expected in tools_used, f"agent should call {expected}"

    assert all(a["status"] == "completed" for a in actions)
    assert "MR !" in reply
    assert "Playbook followed" in reply


def test_scripted_deploy_holds_when_not_all_green():
    agent = AgentService()
    _, reply = _collect(agent, "deploy for metlife, there's a match tonight", "d")
    # stadium-dashboard is 'running' in a fresh world → must HOLD.
    assert "HELD" in reply or "Blockers" in reply


def test_scripted_status_reports_health():
    agent = AgentService()
    _, reply = _collect(agent, "what is the platform health?", "s")
    assert "Platform Health" in reply
    assert "green" in reply.lower()

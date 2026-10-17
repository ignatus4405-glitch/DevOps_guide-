"""Учебные workflow и политики должны быть полными, корректно структурированными примерами."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def task_by_id(course, task_id: str):
    return next(task for module in course.modules for task in module.practice.tasks if task.tid == task_id)


def test_ci_cd_practice_workflows_are_valid_yaml_and_have_steps(course):
    for task_id in ("matrix-artifact", "test-matrix", "capstone-ci"):
        workflow = yaml.load(task_by_id(course, task_id).solution, Loader=yaml.BaseLoader)
        assert isinstance(workflow, dict), task_id
        assert workflow.get("name"), task_id
        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict) and jobs, task_id
        for job_name, job in jobs.items():
            assert isinstance(job.get("steps"), list) and job["steps"], f"{task_id}/{job_name}: нет steps"


def test_capstone_workflow_has_cluster_setup_and_safe_rollback(course):
    workflow = yaml.load(task_by_id(course, "capstone-ci").solution, Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    for job_name in ("staging", "prod", "rollback-drill"):
        steps = jobs[job_name]["steps"]
        assert any(step.get("uses", "").startswith("actions/checkout@") for step in steps)
        assert any("KUBECONFIG_B64" in step.get("env", {}) for step in steps)
    rollback = jobs["rollback-drill"]
    assert "workflow_dispatch" in workflow["on"]
    assert any("rollout undo" in step.get("run", "") for step in rollback["steps"])


def test_terraform_backend_iam_example_is_scoped_to_state_and_lock_objects():
    policy_path = ROOT / "content/modules/08-iac/examples/state/backend-iam-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    statements = {statement["Sid"]: statement for statement in policy["Statement"]}
    state_statement = statements["ReadWriteState"]
    lock_statement = statements["ManageOnlyLockFile"]

    assert state_statement["Action"] == ["s3:GetObject", "s3:PutObject"]
    assert "s3:DeleteObject" not in state_statement["Action"]
    assert "s3:DeleteObject" in lock_statement["Action"]
    assert state_statement["Resource"].endswith("terraform.tfstate")
    assert lock_statement["Resource"].endswith("terraform.tfstate.tflock")


def test_terraform_policy_examples_are_valid_and_cover_allow_and_deny_cases():
    examples = ROOT / "content/modules/08-iac/examples/policy"
    safe = json.loads((examples / "plan-safe.json").read_text(encoding="utf-8"))
    unsafe = json.loads((examples / "plan-public-ssh.json").read_text(encoding="utf-8"))
    policy = (examples / "ssh.rego").read_text(encoding="utf-8")

    assert safe["resource_changes"][0]["change"]["after"]["cidr_blocks"] != ["0.0.0.0/0"]
    public_ssh = unsafe["resource_changes"][0]
    assert public_ssh["change"]["after"]["cidr_blocks"] == ["0.0.0.0/0"]
    assert public_ssh["change"]["after"]["from_port"] == 22
    assert "package terraform" in policy
    assert "deny contains msg if {" in policy
    assert 'resource.change.after.cidr_blocks[_] == "0.0.0.0/0"' in policy


def test_terraform_tag_policy_fixtures_cover_valid_and_missing_owner():
    examples = ROOT / "content/modules/08-iac/examples/tags"
    with_owner = json.loads((examples / "plan-with-owner.json").read_text(encoding="utf-8"))
    without_owner = json.loads((examples / "plan-without-owner.json").read_text(encoding="utf-8"))
    policy = (examples / "tags.rego").read_text(encoding="utf-8")
    assert with_owner["resource_changes"][0]["change"]["after"]["tags"]["owner"]
    assert "owner" not in without_owner["resource_changes"][0]["change"]["after"]["tags"]
    assert "package main" in policy
    assert "deny contains msg if {" in policy
    assert 'owner := object.get(tags, "owner", "")' in policy
    assert 'owner == ""' in policy


def test_repository_workflows_parse_as_yaml():
    for workflow_path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(workflow, dict), workflow_path.name
        assert isinstance(workflow.get("jobs"), dict) and workflow["jobs"], workflow_path.name


def test_release_workflow_uses_one_prepared_commit_and_main_only():
    workflow_path = ROOT / ".github/workflows/build.yml"
    workflow = yaml.load(workflow_path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    jobs = workflow["jobs"]
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    assert "main" in workflow["on"]["push"]["branches"]
    assert jobs["guard"]["if"] == "github.ref == 'refs/heads/main'"
    assert "refs/heads/main" in workflow_path.read_text(encoding="utf-8")
    assert jobs["guard"]["outputs"]["sha"] == "${{ steps.release_commit.outputs.sha }}"
    assert jobs["guard"]["permissions"]["contents"] == "write"
    assert jobs["release"]["permissions"]["contents"] == "write"
    for job_name in ("windows", "linux"):
        assert jobs[job_name]["steps"][0]["with"]["ref"] == "${{ needs.guard.outputs.sha }}"
    release_text = "\n".join(step.get("run", "") for step in jobs["release"]["steps"])
    assert 'git tag -a "v$VERSION" "$RELEASE_SHA"' in release_text
    assert "git push origin HEAD:main" not in release_text
    preparation = jobs["guard"]["steps"]
    commit_step = next(step for step in preparation if step.get("id") == "release_commit")
    assert "git push origin HEAD:main" in commit_step["run"]

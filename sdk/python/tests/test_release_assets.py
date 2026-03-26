from __future__ import annotations

from pathlib import Path
import subprocess

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_static_application_document_matches_current_repo_story() -> None:
    document_path = REPO_ROOT / "docs" / "application-document.html"

    assert document_path.exists()
    html = document_path.read_text()

    assert "Python-only backend library and SDK wrapper" in html
    assert "web_agent_backend" in html
    assert "ChatOpenAI" in html
    assert "docs/assets/readme-backend-sdk-workflow.svg" in html


def test_pages_workflow_publishes_the_current_svg_asset() -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "pages.yml"

    assert workflow_path.exists()
    workflow = workflow_path.read_text()

    assert "docs/assets/readme-backend-sdk-workflow.svg" in workflow
    assert "_site/docs/assets/readme-backend-sdk-workflow.svg" in workflow


def test_pages_workflow_enables_pages_for_first_deploy() -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "pages.yml"

    assert workflow_path.exists()
    workflow = workflow_path.read_text()

    assert "uses: actions/configure-pages@v5" in workflow
    assert "enablement: true" in workflow


def test_release_workflow_invokes_script_via_bash() -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "release-sdk.yml"

    assert workflow_path.exists()
    workflow = workflow_path.read_text()

    assert "run: bash ./scripts/release_sdk.sh" in workflow


def test_release_script_rejects_mismatched_release_tag() -> None:
    script_path = REPO_ROOT / "scripts" / "release_sdk.sh"

    with pytest.raises(subprocess.CalledProcessError) as error_info:
        subprocess.run(
            ["bash", str(script_path)],
            cwd=REPO_ROOT,
            env={
                **dict(__import__("os").environ),
                "RELEASE_TAG": "web-agent-sdk-v9.9.9",
            },
            check=True,
            text=True,
            capture_output=True,
        )

    assert "release tag mismatch" in error_info.value.stderr

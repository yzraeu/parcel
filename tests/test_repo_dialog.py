"""Tests for the add-repository dialog and its fingerprint confirmation."""

from __future__ import annotations

from parcel.backend.models import RepoKind, RepoPlan, RepoRequest
from parcel.ui.repo_dialog import AddRepoDialog

FINGERPRINT = "0123456789ABCDEF0123456789ABCDEF01234567"


def make_plan() -> RepoPlan:
    request = RepoRequest(kind=RepoKind.COPR, copr="owner/project")
    return RepoPlan(
        request=request,
        repo_id="copr:copr.fedorainfracloud.org:owner:project",
        name="Copr repo for project owned by owner",
        baseurl="https://copr.example/owner/project/",
        key_url="https://download.example/pubkey.gpg",
        key_fingerprint=FINGERPRINT,
        key_id="KEYID",
        repo_file_name="_copr:owner:project.repo",
        repo_file="[copr:owner:project]\n",
        key_data=b"KEY",
        command=("pkexec", "dnf", "copr", "enable", "-y", "owner/project"),
    )


def make_dialog() -> AddRepoDialog:
    dialog = AddRepoDialog(
        on_prepare=lambda request: dialog.prepared.append(request),
        on_confirm=lambda plan: dialog.confirmed.append(plan),
    )
    dialog.prepared = []  # type: ignore[attr-defined]
    dialog.confirmed = []  # type: ignore[attr-defined]
    return dialog


def test_copr_is_the_default_form() -> None:
    dialog = make_dialog()

    assert dialog.mode_stack.get_visible_child_name() == "copr"
    assert dialog.content_stack.get_visible_child_name() == "form"
    assert dialog.add_button.get_visible()
    assert not dialog.trust_button.get_visible()


def test_copr_form_requires_a_project() -> None:
    dialog = make_dialog()

    dialog.add_button.emit("clicked")

    assert dialog.prepared == []
    assert dialog.error_label.get_visible()
    assert "owner/project" in dialog.error_label.get_label()


def test_copr_form_forwards_owner_project() -> None:
    dialog = make_dialog()
    dialog.copr_entry.set_text(" owner/project ")

    dialog.add_button.emit("clicked")

    assert dialog.prepared == [RepoRequest(kind=RepoKind.COPR, copr="owner/project")]


def test_url_form_forwards_name_and_base_url() -> None:
    dialog = make_dialog()
    dialog.mode_stack.set_visible_child_name("url")
    dialog.name_entry.set_text("myrepo")
    dialog.url_entry.set_text("https://example.com/repo/")

    dialog.add_button.emit("clicked")

    assert dialog.prepared == [
        RepoRequest(
            kind=RepoKind.URL,
            name="myrepo",
            baseurl="https://example.com/repo/",
        )
    ]


def test_url_form_requires_both_fields() -> None:
    dialog = make_dialog()
    dialog.mode_stack.set_visible_child_name("url")
    dialog.name_entry.set_text("myrepo")

    dialog.add_button.emit("clicked")

    assert dialog.prepared == []
    assert dialog.error_label.get_visible()


def test_confirm_page_shows_the_fingerprint_and_key_identity() -> None:
    dialog = make_dialog()
    plan = make_plan()

    dialog.show_plan(plan)

    assert dialog.content_stack.get_visible_child_name() == "confirm"
    assert not dialog.mode_switcher.get_visible()
    assert dialog.fingerprint_label.get_label() == (
        "0123 4567 89AB CDEF 0123 4567 89AB CDEF 0123 4567"
    )
    assert dialog.key_id_label.get_label() == "Key ID KEYID"
    assert dialog.key_url_label.get_label() == "https://download.example/pubkey.gpg"
    assert dialog.trust_button.get_visible()
    assert not dialog.add_button.get_visible()


def test_trust_is_what_forwards_the_plan() -> None:
    dialog = make_dialog()
    plan = make_plan()
    dialog.show_plan(plan)

    assert dialog.confirmed == []
    dialog.trust_button.emit("clicked")

    assert dialog.confirmed == [plan]


def test_back_returns_to_the_form_without_adding() -> None:
    dialog = make_dialog()
    dialog.show_plan(make_plan())

    dialog.back_button.emit("clicked")

    assert dialog.plan is None
    assert dialog.content_stack.get_visible_child_name() == "form"
    assert dialog.mode_switcher.get_visible()
    assert dialog.add_button.get_visible()
    assert not dialog.trust_button.get_visible()
    assert dialog.confirmed == []


def test_errors_are_shown_and_reenable_the_buttons() -> None:
    dialog = make_dialog()
    dialog.set_busy(True)

    dialog.show_error(RuntimeError("the key did not download"))

    assert dialog.error_label.get_visible()
    assert dialog.error_label.get_label() == "the key did not download"
    assert dialog.add_button.get_sensitive()
    assert dialog.trust_button.get_sensitive()


def test_busy_state_disables_actions_and_shows_the_spinner() -> None:
    dialog = make_dialog()

    dialog.set_busy(True)

    assert not dialog.add_button.get_sensitive()
    assert not dialog.trust_button.get_sensitive()
    assert dialog.spinner.get_visible()

    dialog.set_busy(False)

    assert dialog.add_button.get_sensitive()
    assert not dialog.spinner.get_visible()


def test_trust_without_a_plan_is_an_error() -> None:
    dialog = make_dialog()

    dialog.trust_button.emit("clicked")

    assert dialog.confirmed == []
    assert dialog.error_label.get_visible()

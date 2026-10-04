"""G2 contracts, no network or live factory trigger."""
import pytest
from app.corporate import Actor, GuardError, PilotAdapter, validate_intake, repository_contract


def test_registry_is_exact_repository_id_and_canonical_name():
    assert repository_contract() == {"id": 1109489408, "name": "astro-dev-lab/me-fastapi"}


@pytest.mark.parametrize("actor", [Actor("bot-1", "service"), Actor("reviewer-1", "service"), Actor("other", "human")])
def test_only_designated_human_owner_can_approve(actor):
    with pytest.raises(GuardError): actor.require_owner("owner")


def test_owner_may_submit_and_explicitly_approve_own_request():
    assert Actor("owner", "human").require_owner("owner") is None


@pytest.mark.parametrize("field,value", [("title", ""), ("objective", "https://token@example.com"), ("acceptance", "Authorization: Bearer synthetic-secret"), ("title", "a" * 121)])
def test_intake_rejects_invalid_or_credential_shaped_records(field, value):
    data = {"title": "Synthetic task", "objective": "Improve a local calculation", "acceptance": "All local tests pass"}
    data[field] = value
    with pytest.raises(GuardError): validate_intake(data)


def test_pilot_contract_deduplicates_and_never_dispatches_live():
    adapter = PilotAdapter()
    a = adapter.ensure_issue(repository_contract(), "work-1", {"title": "Synthetic"})
    b = adapter.ensure_issue(repository_contract(), "work-1", {"title": "Synthetic"})
    assert a == b and len(adapter.issues) == 1
    assert a.startswith("contract-")
    with pytest.raises(GuardError): adapter.live_dispatch(a)
    assert adapter.dispatch_status == "BLOCKED_UPSTREAM_AUTHORIZATION"


def test_pilot_rejects_arbitrary_repository():
    with pytest.raises(GuardError): PilotAdapter().ensure_issue({"id": 1, "name": "attacker/repo"}, "work", {})


def test_contract_flow_with_network_connections_denied(monkeypatch):
    import socket
    def denied(*args,**kwargs): raise AssertionError('G2 vendor egress forbidden')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)
    monkeypatch.setattr(socket,'getaddrinfo',denied)
    adapter=PilotAdapter()
    assert adapter.ensure_issue(repository_contract(),'synthetic-work',{'title':'Synthetic'}).startswith('contract-')
    with pytest.raises(GuardError): adapter.live_dispatch('contract-proof')

import json
import pytest

from apps.rag.services import chat_service as cs


def test_extract_service_items_empty(monkeypatch):
    monkeypatch.setattr(cs, "generate_llm", lambda messages, config_name=None, temperature=None: '{"items": []}')
    items = cs._extract_service_items_with_llm("saya mau pesan")
    assert items == []


def test_extract_service_items_cctv(monkeypatch):
    monkeypatch.setattr(cs, "generate_llm", lambda messages, config_name=None, temperature=None: '{"items": ["CCTV"]}')
    items = cs._extract_service_items_with_llm("cctv keknya perlu di pasang di retail deh, orderin ya")
    assert items == ["CCTV"]


def test_extract_service_items_typo(monkeypatch):
    # LLM should normalize/understand typo 'pyoyektor' -> 'Proyektor'
    monkeypatch.setattr(cs, "generate_llm", lambda messages, config_name=None, temperature=None: '{"items": ["Proyektor"]}')
    items = cs._extract_service_items_with_llm("mau order pyoyektor baru")
    assert items == ["Proyektor"]


def test_rewrite_query_for_rag_device_symptom(monkeypatch):
    monkeypatch.setattr(
        cs,
        "generate_llm",
        lambda messages, config_name=None, temperature=None: '{"rewritten":"wifi tidak nyambung","device":"PC","symptom":"wifi tidak nyambung"}'
    )
    rewritten, device, symptom = cs.rewrite_query_for_rag("pc saya rusak, wifinya gk mau nyambung", [])
    assert "wifi" in rewritten
    assert device == "PC"
    assert "wifi" in symptom


def test_build_sop_system_msg_includes_device_note():
    msg = cs._build_sop_system_msg("dummy context", [], user_device="PC")
    assert "Pengguna menyebut perangkat: PC" in msg

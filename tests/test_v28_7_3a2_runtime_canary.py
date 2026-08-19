from project_domain_reader import READ_PATH_VERSION


def test_reader_version_is_a2():
    assert READ_PATH_VERSION == "V28.7.3A2"


def test_canary_page_is_shadow_only():
    text = open("pages/15_Domain_Read_Canary.py", encoding="utf-8").read()
    assert 'legacy_loader=lambda: []' in text
    assert 'audit_scope=CANARY_SCOPE' in text
    assert '"domain_primary"' not in text
    assert 'result.domain_candidate' in text


def test_canary_verifier_requires_zero_fallback():
    text = open("NAVE_V28_7_3A2_VERIFY_RUNTIME_SHADOW_CANARY.sql", encoding="utf-8").read()
    assert "zero_runtime_fallback" in text
    assert "chambinho_zero_journey_probed_without_fallback" in text
    assert "zero_domain_primary" in text

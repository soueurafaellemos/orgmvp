from project_requirement_identity_supersession_dry_run import occurrence_hash

def test_occurrence_hash_depends_on_requirement_identity():
    a = occurrence_hash("p", "old", "e", "requirement")
    b = occurrence_hash("p", "new", "e", "requirement")
    assert a != b

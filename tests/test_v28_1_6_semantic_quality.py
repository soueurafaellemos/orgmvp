import types
import sys

if "supabase" not in sys.modules:
    supabase_stub = types.ModuleType("supabase")
    supabase_stub.Client = object
    sys.modules["supabase"] = supabase_stub

try:
    import google
except ImportError:
    google = types.ModuleType("google")

if not hasattr(google, "genai"):
    google.genai = types.SimpleNamespace(Client=object)

from memory_models import MemoryBatch


def _materializer():
    from project_bundle_materializer import _sanitize_memory_items
    return _sanitize_memory_items


def _extractor():
    from memory_extractor import _candidate_items, _repair_batch_coverage
    return _candidate_items, _repair_batch_coverage


def test_semantic_sanitizer_keeps_proposal_sections_clean():
    sanitize = _materializer()
    items = [
        {"section_key": "strategy", "title": "Estratégia — slide 5", "summary": "Registro visual da proposta", "source_page": 5},
        {"section_key": "strategy", "title": "Banda", "summary": "Banda Studio 4 com repertório versátil", "source_page": 20},
        {"section_key": "gifts", "title": "Bourbon Atibaia", "summary": "Ballroom Garden I & II e montagem", "source_page": 4},
        {"section_key": "gifts", "title": "Jantar temático 1", "summary": "Mangia que te fa benne, massas e risottos", "source_page": 30},
        {"section_key": "gifts", "title": "Kit", "summary": "Kit de boas-vindas com 3 camisetas", "source_page": 40},
        {"section_key": "strategy", "title": "Bacio di Latte", "summary": "Experiências & Ativações com picolés Bacio di Latte", "source_page": 33},
    ]
    cleaned = sanitize(items)
    assert len(cleaned) == 5
    by_title = {row["title"]: row for row in cleaned}
    assert by_title["Banda"]["section_key"] == "content_agenda"
    assert by_title["Bourbon Atibaia"]["section_key"] == "journey_operation"
    assert by_title["Jantar temático 1"]["section_key"] == "content_agenda"
    assert by_title["Kit"]["section_key"] == "gifts"
    assert by_title["Bacio di Latte"]["section_key"] == "activations"
    assert all(row["status"] == "Proposto" for row in cleaned)


def test_palco_is_not_contaminated_by_other_labels_on_same_plant():
    sanitize = _materializer()
    cleaned = sanitize([{
        "section_key": "activations",
        "title": "Palco",
        "summary": "ILHA DE MASSAGEM PALCO h=0,80m PHOTO OP 10x4m TOTEM LED 2x3m",
        "description": "ILHA DE MASSAGEM PALCO h=0,80m PHOTO OP 10x4m TOTEM LED 2x3m BUFFET",
        "source_page": 17,
    }])
    assert cleaned[0]["section_key"] == "scenography"
    assert cleaned[0]["status"] == "Proposto"


def test_extractor_does_not_use_isolated_kit_as_gift_candidate():
    candidate_items, _ = _extractor()
    assert not any(row["section_key"] == "gifts" for row in candidate_items("kit técnico de montagem"))
    candidates = candidate_items("Kit de boas-vindas — 3 camisetas e mala para esportes")
    assert any(row["section_key"] == "gifts" for row in candidates)


def test_extractor_recognizes_planeja_entities_separately():
    candidate_items, _ = _extractor()
    candidates = candidate_items(
        "ILHA DE MASSAGEM 250 lugares PALCO h=0,80m PHOTO OP 10x4m TOTEM LED 2x3m BAR DE CAFÉS"
    )
    titles = {row["title"] for row in candidates}
    assert "Quick Massage" in titles
    assert "Palco" in titles
    assert "Ponto de foto" in titles
    assert "Totem" in titles
    assert "Bar de cafés" in titles


def test_repair_does_not_fabricate_generic_item_for_context_only_page():
    _, repair_batch_coverage = _extractor()
    inventory = [{
        "page_number": 5,
        "suggested_title": "Contexto do evento",
        "summary": "Contexto visual sem entidade independente.",
        "suggested_section": "strategy",
        "is_meaningful": True,
        "exclusion_reason": None,
        "content_kind": "visual",
        "candidate_items": [],
        "normalized_text": "contexto do evento",
        "section_score": 0,
        "text": "Contexto do evento",
        "source_file": "proposta.pdf",
        "image_count": 1,
        "text_length": 18,
        "anchor_label": None,
        "expected_min_items": 0,
    }]
    batch = repair_batch_coverage(
        MemoryBatch(source_file="proposta.pdf", slides=[]),
        source_file="proposta.pdf",
        inventory_rows=inventory,
    )
    assert len(batch.slides) == 1
    assert batch.slides[0].is_meaningful is True
    assert batch.slides[0].items == []
    assert batch.coverage["automatic_repair_items"] == 0

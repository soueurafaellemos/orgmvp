from supplier_visibility import is_visible_supplier


def test_venue_stub_same_name_is_hidden():
    supplier = {"name": "Allianz Parque"}
    assert is_visible_supplier(supplier, linked_venue_names=["Allianz Parque"]) is False


def test_real_supplier_with_product_is_visible_even_if_operates_venue():
    supplier = {"name": "Fornecedor X"}
    assert is_visible_supplier(supplier, linked_venue_names=["Fornecedor X"], products_count=1) is True


def test_supplier_linked_to_different_named_venue_is_visible():
    supplier = {"name": "Operadora XYZ"}
    assert is_visible_supplier(supplier, linked_venue_names=["Casa de Eventos XYZ"]) is True


def test_supplier_with_contact_is_visible():
    supplier = {"name": "Fornecedor X", "email": "contato@example.com"}
    assert is_visible_supplier(supplier, linked_venue_names=["Fornecedor X"]) is True


def test_supplier_not_linked_to_venue_is_visible():
    assert is_visible_supplier({"name": "TechnoMotion"}, linked_venue_names=[]) is True

import os
import re

def test_no_ocr_in_public_ui():
    """Verify that app.py does not contain public OCR instructions or legacy terms."""
    app_path = "app.py"
    assert os.path.exists(app_path), "app.py does not exist"
    
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Terms that should not appear in the public UI code (app.py)
    forbidden_terms = [
        "Método de Envio",
        "OCR / Imagens (Legado)",
        "Tire 2 prints",
        "Tire prints",
        "Copie o texto",
        "Acesse o simulador do ge",
        "Abrir simulador do ge",
        "Dicas para o OCR",
        "OCR / Imagens",
    ]
    
    for term in forbidden_terms:
        # Check if term appears in a case-insensitive search
        match = re.search(re.escape(term), content, re.IGNORECASE)
        assert match is None, f"Forbidden term '{term}' found in app.py"

def test_no_double_asterisks_as_fallback():
    """Verify that there is no '**' fallback string used for empty stadiums in ui_simulator.py."""
    simulator_path = os.path.join("src", "bolao", "ui_simulator.py")
    assert os.path.exists(simulator_path), "ui_simulator.py does not exist"
    
    with open(simulator_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check for formatting patterns that could render '**'
    # For example, checking if we format empty values as '**' or if we check if stadium is empty.
    # We should NOT see ' - **' or ' · **' or similar fallback templates in the rendering code.
    assert " - **" not in content
    assert " · **" not in content
    assert " · **" not in content

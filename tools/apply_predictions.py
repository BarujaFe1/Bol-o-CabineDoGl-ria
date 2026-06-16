import os
import sys
from pathlib import Path

# Add project root to python path to import modules
sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.bolao.storage import upsert_live_prediction

predictions = [
    # Nikolas
    ("Nikolas", "13383", 0, 2),
    ("Nikolas", "13384", 3, 1),
    ("Nikolas", "13385", 1, 2),
    ("Nikolas", "13386", 1, 1),
    ("Nikolas", "13387", 2, 0),
    ("Nikolas", "13388", 2, 1),
    ("Nikolas", "13389", 0, 2),
    
    # Murilov
    ("Murilov", "13381", 1, 1),
    ("Murilov", "13382", 1, 1),
    
    # Mantovas
    ("Mantovas", "13382", 0, 1),
    
    # Lucão
    ("Lucão", "13381", 2, 0),
    ("Lucão", "13382", 1, 0),
    
    # Jonaldo, o Fenômeno
    ("Jonaldo, o Fenômeno", "13382", 4, 0),
    ("Jonaldo, o Fenômeno", "13384", 1, 0),
    ("Jonaldo, o Fenômeno", "13385", 0, 2),
    ("Jonaldo, o Fenômeno", "13386", 1, 1),
    ("Jonaldo, o Fenômeno", "13387", 5, 0),
]

print("Aplicando palpites jogo a jogo...")
for user, match, home, away in predictions:
    pred = upsert_live_prediction(participant_name=user, match_id=match, home_goals=home, away_goals=away)
    print(f"  [OK] {user} - Match {match}: {home} x {away} (Chave: {pred.participant_key})")
print("Todos os palpites foram aplicados com sucesso!")

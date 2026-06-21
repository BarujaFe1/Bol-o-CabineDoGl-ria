from __future__ import annotations

APP_NAME = "Bolão da Cabine do Glória"
APP_SUBTITLE = "Copa do Mundo 2026"
GE_SIMULATOR_URL = "https://interativos.ge.globo.com/futebol/copa-do-mundo/especial/simulador-da-copa-do-mundo-2026"

GROUPS = list("ABCDEFGHIJKL")

PHASES = ["fase_32", "oitavas", "quartas", "semifinais", "final"]

PHASE_LABELS = {
    "fase_32": "Décima-sextas",
    "oitavas": "Oitavas",
    "quartas": "Quartas",
    "semifinais": "Semi",
    "final": "Final",
}

PHASE_ALIASES = {
    "decima-sextas": "fase_32",
    "decima sextas": "fase_32",
    "decimas-sextas": "fase_32",
    "decimas sextas": "fase_32",
    "dezesseis avos": "fase_32",
    "16 avos": "fase_32",
    "16-avos": "fase_32",
    "16avos": "fase_32",
    "fase de 32": "fase_32",
    "32": "fase_32",
    "oitavas": "oitavas",
    "oitavas de final": "oitavas",
    "quartas": "quartas",
    "quartas de final": "quartas",
    "semi": "semifinais",
    "semis": "semifinais",
    "semifinal": "semifinais",
    "semifinais": "semifinais",
    "final": "final",
}

CHAMPION_ALIASES = {"campea", "campeao", "campeã", "campeão"}

# Ordem visual fixa usada pelo simulador do ge nos cards de grupo.
# O parser de imagem usa essa ordem + a cor da linha para descobrir 1º, 2º, 3º e 4º.
GE_GROUP_ROW_ORDER = {
    "A": ["México", "África do Sul", "Coreia do Sul", "Rep. Tcheca"],
    "B": ["Canadá", "Bósnia", "Catar", "Suíça"],
    "C": ["Brasil", "Marrocos", "Haiti", "Escócia"],
    "D": ["EUA", "Paraguai", "Austrália", "Turquia"],
    "E": ["Alemanha", "Curaçao", "Costa do Marfim", "Equador"],
    "F": ["Holanda", "Japão", "Suécia", "Tunísia"],
    "G": ["Bélgica", "Egito", "Irã", "Nova Zelândia"],
    "H": ["Espanha", "Cabo Verde", "Arábia Saudita", "Uruguai"],
    "I": ["França", "Senegal", "Iraque", "Noruega"],
    "J": ["Argentina", "Argélia", "Áustria", "Jordânia"],
    "K": ["Portugal", "RD Congo", "Uzbequistão", "Colômbia"],
    "L": ["Inglaterra", "Croácia", "Gana", "Panamá"],
}

TEAM_ALIASES = {
    "México": ["mexico", "méxico", "mex", "méx"],
    "África do Sul": ["africa do sul", "áfrica do sul", "afs", "rsa", "south africa"],
    "Coreia do Sul": ["coreia do sul", "coréia do sul", "coreia", "coreia sul", "cor", "kor", "korea republic"],
    "Rep. Tcheca": ["republica tcheca", "república tcheca", "rep tcheca", "rep. tcheca", "tcheca", "cze", "czechia", "chequia"],
    "Catar": ["catar", "qatar", "cat", "qat"],
    "Suíça": ["suica", "suíça", "sui", "suiça", "switzerland"],
    "Canadá": ["canada", "canadá", "can"],
    "Bósnia": ["bosnia", "bósnia", "bosnia e herzegovina", "bósnia e herzegovina", "bos", "bih"],
    "Brasil": ["brasil", "bra", "brazil"],
    "Marrocos": ["marrocos", "mar", "morocco"],
    "Haiti": ["haiti", "haití", "hai"],
    "Escócia": ["escocia", "escócia", "esc", "sco", "scotland"],
    "EUA": ["eua", "estados unidos", "usa", "united states", "estados unidos da america", "u s a"],
    "Paraguai": ["paraguai", "par", "paraguay"],
    "Austrália": ["australia", "austrália", "aus"],
    "Turquia": ["turquia", "turkiye", "türkiye", "tur", "turkey"],
    "Alemanha": ["alemanha", "ale", "ger", "germany"],
    "Curaçao": ["curacao", "curaçao", "cur"],
    "Costa do Marfim": ["costa do marfim", "cote d ivoire", "côte d'ivoire", "marfim", "cdm", "civ"],
    "Equador": ["equador", "equ", "ecuador", "ecu"],
    "Holanda": ["holanda", "paises baixos", "países baixos", "netherlands", "hol", "ned"],
    "Japão": ["japao", "japão", "jap", "japan", "jpn"],
    "Tunísia": ["tunisia", "tunísia", "tun"],
    "Suécia": ["suecia", "suécia", "swe", "sue", "sweden"],
    "Bélgica": ["belgica", "bélgica", "bel", "belgium"],
    "Irã": ["ira", "irã", "iran", "irn"],
    "Egito": ["egito", "egi", "egypt", "egy"],
    "Nova Zelândia": ["nova zelandia", "nova zelândia", "nzl", "new zealand"],
    "Espanha": ["espanha", "esp", "spain"],
    "Cabo Verde": ["cabo verde", "cab", "cpv", "cape verde"],
    "Arábia Saudita": ["arabia saudita", "arábia saudita", "ara", "ksa", "saudi arabia"],
    "Uruguai": ["uruguai", "uru", "uruguay"],
    "França": ["franca", "frança", "fra", "france"],
    "Senegal": ["senegal", "sen"],
    "Noruega": ["noruega", "nor", "norway"],
    "Iraque": ["iraque", "irq", "iraq"],
    "Argentina": ["argentina", "arg"],
    "Argélia": ["argelia", "argélia", "agl", "alg", "algeria"],
    "Áustria": ["austria", "áustria", "aut"],
    "Jordânia": ["jordania", "jordânia", "jor", "jordan"],
    "Portugal": ["portugal", "por"],
    "Uzbequistão": ["uzbequistao", "uzbequistão", "uzb", "uzbekistan"],
    "Colômbia": ["colombia", "colômbia", "col"],
    "RD Congo": ["rd congo", "republica democratica do congo", "república democrática do congo", "congo dr", "drc", "rdc", "cod"],
    "Inglaterra": ["inglaterra", "ing", "england", "eng"],
    "Croácia": ["croacia", "croácia", "cro", "croatia"],
    "Gana": ["gana", "gan", "gha", "ghana"],
    "Panamá": ["panama", "panamá", "pan"],
}

ALL_TEAMS = list(TEAM_ALIASES.keys())

# ── Label mappers for UI (never expose internal keys to users) ──

SCORING_LABELS = {
    "group_1": "Acertar 1\u00ba Lugar do Grupo",
    "group_2": "Acertar 2\u00ba Lugar do Grupo",
    "group_3_best": "Acertar 3\u00ba Lugar (Melhor Terceiro)",
    "best_third": "Acertar Melhor Terceiro Classificado",
    "fase_32": "Classificar Fase das 32",
    "oitavas": "Classificar Oitavas de Final",
    "quartas": "Classificar Quartas de Final",
    "semifinais": "Classificar Semifinais",
    "final": "Classificar Final",
    "champion_bonus": "B\u00f4nus de Campe\u00e3o",
    "decision_points": "Pontos por Decis\u00e3o",
}

STATUS_LABELS = {
    "scheduled": "Agendado",
    "locked": "Fechado",
    "live": "Ao Vivo",
    "finished": "Finalizado",
    "result_approved": "Resultado Aprovado",
}

SCORING_MODE_LABELS = {
    "isolated_max": "M\u00e1ximo Isolado (placar exato bloqueia ac\u00famulo)",
    "additive": "Cumulativo (soma todos os crit\u00e9rios acertados)",
}

SCORING_MODE_OPTIONS = {
    "v2": "V2 (Recomendado)",
    "ponderado": "Ponderado (Legado)",
    "uniforme": "Uniforme (Legado)",
}

DEFAULT_WEIGHTED_RULES = {
    "group_1": 5,
    "group_2": 3,
    "group_3_best": 2,
    "best_third": 2,
    "fase_32": 5,
    "oitavas": 5,
    "quartas": 5,
    "semifinais": 5,
    "final": 5,
    "champion_bonus": 0,
}

DEFAULT_UNIFORM_RULES = {
    "decision_points": 1,
    "champion_bonus": 0,
}

DEFAULT_V2_RULES = {
    "group_exact": 5,
    "group_result_gd": 3,
    "group_result": 2,
    "group_team_goals": 1,
    "group_sum_goals": 0,
    "group_both_scored": 0,
    "group_over_2_5": 0,
    "ko_oitavas": 3,
    "ko_quartas": 5,
    "ko_semifinais": 8,
    "ko_final": 12,
    "ko_champion": 20,
}

ACTIVE_PARTICIPANT_NAMES = ["Baruja", "Fantato", "Henrique", "Murilov", "Lucão", "Mantovas", "Jonaldo, o Fenômeno", "Nikolas"]

ELENCO_BRASIL_2026 = [
    {"camisa": 1,  "nome": "Alisson",           "posicao": "GOL", "ativo": True},
    {"camisa": 2,  "nome": "Éderson",            "posicao": "DEF", "ativo": True},  # substituiu Wesley
    {"camisa": 3,  "nome": "Gabriel Magalhães",  "posicao": "DEF", "ativo": True},
    {"camisa": 4,  "nome": "Marquinhos",         "posicao": "DEF", "ativo": True},
    {"camisa": 5,  "nome": "Casemiro",           "posicao": "MEI", "ativo": True},
    {"camisa": 6,  "nome": "Alex Sandro",        "posicao": "DEF", "ativo": True},
    {"camisa": 7,  "nome": "Vini Jr.",           "posicao": "ATA", "ativo": True},
    {"camisa": 8,  "nome": "Bruno Guimarães",    "posicao": "MEI", "ativo": True},
    {"camisa": 9,  "nome": "Matheus Cunha",      "posicao": "ATA", "ativo": True},
    {"camisa": 10, "nome": "Neymar",             "posicao": "ATA", "ativo": True},
    {"camisa": 11, "nome": "Raphinha",           "posicao": "ATA", "ativo": True},
    {"camisa": 12, "nome": "Weverton",           "posicao": "GOL", "ativo": True},
    {"camisa": 13, "nome": "Danilo",             "posicao": "DEF", "ativo": True},
    {"camisa": 14, "nome": "Bremer",             "posicao": "DEF", "ativo": True},
    {"camisa": 15, "nome": "Léo Pereira",        "posicao": "DEF", "ativo": True},
    {"camisa": 16, "nome": "Douglas Santos",     "posicao": "DEF", "ativo": True},
    {"camisa": 17, "nome": "Fabinho",            "posicao": "MEI", "ativo": True},
    {"camisa": 18, "nome": "Danilo Santos",      "posicao": "MEI", "ativo": True},
    {"camisa": 19, "nome": "Endrick",            "posicao": "ATA", "ativo": True},
    {"camisa": 20, "nome": "Lucas Paquetá",      "posicao": "MEI", "ativo": True},
    {"camisa": 21, "nome": "Luiz Henrique",      "posicao": "ATA", "ativo": True},
    {"camisa": 22, "nome": "Gabriel Martinelli", "posicao": "ATA", "ativo": True},
    {"camisa": 23, "nome": "Ederson Moraes",     "posicao": "GOL", "ativo": True},
    {"camisa": 24, "nome": "Ibañez",             "posicao": "DEF", "ativo": True},
    {"camisa": 25, "nome": "Igor Thiago",        "posicao": "ATA", "ativo": True},
    {"camisa": 26, "nome": "Rayan",              "posicao": "ATA", "ativo": True},
]

VENUES_COPA_2026 = {
    "MetLife Stadium":       {"cidade": "East Rutherford, NJ", "fuso": "GMT-4", "pais": "🇺🇸"},
    "AT&T Stadium":          {"cidade": "Arlington, TX",       "fuso": "GMT-5", "pais": "🇺🇸"},
    "NRG Stadium":           {"cidade": "Houston, TX",         "fuso": "GMT-5", "pais": "🇺🇸"},
    "SoFi Stadium":          {"cidade": "Inglewood, CA",       "fuso": "GMT-7", "pais": "🇺🇸"},
    "Levi's Stadium":        {"cidade": "Santa Clara, CA",     "fuso": "GMT-7", "pais": "🇺🇸"},
    "Arrowhead Stadium":     {"cidade": "Kansas City, MO",     "fuso": "GMT-5", "pais": "🇺🇸"},
    "Gillette Stadium":      {"cidade": "Foxborough, MA",      "fuso": "GMT-4", "pais": "🇺🇸"},
    "Lincoln Financial":     {"cidade": "Filadélfia, PA",      "fuso": "GMT-4", "pais": "🇺🇸"},
    "Mercedes-Benz Stadium": {"cidade": "Atlanta, GA",         "fuso": "GMT-4", "pais": "🇺🇸"},
    "Allegiant Stadium":     {"cidade": "Las Vegas, NV",       "fuso": "GMT-7", "pais": "🇺🇸"},
    "BC Place":              {"cidade": "Vancouver, BC",       "fuso": "GMT-7", "pais": "🇨🇦"},
    "BMO Field":             {"cidade": "Toronto, ON",         "fuso": "GMT-4", "pais": "🇨🇦"},
    "Stade Olympique":       {"cidade": "Montreal, QC",        "fuso": "GMT-4", "pais": "🇨🇦"},
    "Estadio Azteca":        {"cidade": "Cidade do México",    "fuso": "GMT-6", "pais": "🇲🇽"},
    "Estadio BBVA":          {"cidade": "Monterrey",           "fuso": "GMT-6", "pais": "🇲🇽"},
    "Estadio Akron":         {"cidade": "Guadalajara",         "fuso": "GMT-7", "pais": "🇲🇽"},
}

JOGADORES_COPA_2026 = {
    "França": ["Mbappé", "Griezmann", "Dembélé", "Giroud", "Tchouaméni", "Camavinga", "Hernandez", "Saliba", "Maignan"],
    "Noruega": ["Haaland", "Ødegaard", "Sørloth", "Bob", "Ryerson", "Ajer", "Nyland"],
    "Egito": ["Salah", "Mostafa Mohamed", "Trézéguet", "Elneny", "Marmoush"],
    "Inglaterra": ["Kane", "Bellingham", "Saka", "Foden", "Rice", "Walker", "Stones", "Pickford", "Palmer"],
    "Polônia": ["Lewandowski", "Zielinski", "Szczesny", "Kiwiw", "Frankowski"],
    "Espanha": ["Lamine Yamal", "Rodri", "Pedri", "Gavi", "Morata", "Nico Williams", "Carvajal", "Unai Simón"],
    "Brasil": [j["nome"] for j in ELENCO_BRASIL_2026],
    "Argentina": ["Messi", "Di María", "Lautaro Martínez", "Álvarez", "De Paul", "Enzo Fernández", "Mac Allister", "Romero", "Martínez"],
    "Nigéria": ["Osimhen", "Lookman", "Chukwueze", "Iwobi", "Bassey"],
    "Equador": ["Valencia", "Caicedo", "Hincapié", "Estupiñán"],
    "Colômbia": ["Luis Díaz", "James Rodríguez", "Arias", "Borré", "Lerma"],
    "Alemanha": ["Musiala", "Wirtz", "Havertz", "Kimmich", "Rüdiger", "Ter Stegen", "Sané"],
    "Bélgica": ["De Bruyne", "Lukaku", "Doku", "Trossard", "Tielemans", "Courtois"],
    "Suíça": ["Xhaka", "Akanji", "Sommer", "Embolo", "Shaqiri"],
    "Uruguai": ["Darwin Núñez", "Valverde", "Araújo", "De Arrascaeta", "Bentancur"],
    "Senegal": ["Mané", "Jackson", "Sarr", "Koulibaly", "Mendy"],
    "Croácia": ["Modric", "Kovacic", "Gvardiol", "Kramaric", "Perisic"],
    "Portugal": ["Cristiano Ronaldo", "Bruno Fernandes", "Bernardo Silva", "Leão", "Félix", "Dias", "Costa"],
    "Coreia do Sul": ["Son Heung-min", "Hwang Hee-chan", "Kim Min-jae", "Lee Kang-in"],
    "Suécia": ["Gyökeres", "Isak", "Kulusevski", "Lindelöf", "Olsen"],
    "México": ["Santiago Giménez", "Lozano", "Álvarez", "Ochoa"],
    "Catar": ["Afif", "Almoez Ali", "Al-Haydos"],
    "Japão": ["Mitoma", "Kubo", "Endo", "Minamino", "Tomiyasu"],
    "Paraguai": ["Almirón", "Enciso", "Sanabria", "Gómez"],
    "Panamá": ["Carrasquilla", "Fajardo", "Bárcenas"],
    "Arábia Saudita": ["Al-Dawsari", "Al-Shehri", "Al-Muwallad"],
    "Marrocos": ["Ziyech", "Hakimi", "En-Nesyri", "Bounou", "Diaz"],
    "Austrália": ["Duke", "Irvine", "Souttar", "Ryan"],
    "Irã": ["Taremi", "Azmoun", "Jahanbakhsh"],
    "Tunísia": ["Msakni", "Laïdouni", "Talbi"],
    "África do Sul": ["Tau", "Mokoena", "Zwane"],
    "Holanda": ["Depay", "Gakpo", "Simons", "Van Dijk", "De Ligt", "Verbruggen"],
    "Estados Unidos": ["Pulisic", "McKennie", "Weah", "Dest", "Turner"],
    "Canadá": ["Jonathan David", "Alphonso Davies", "Buchanan", "Eustaquio"],
    "Gana": ["Kudus", "Iñaki Williams", "Partey", "Ayew"],
    "Escócia": ["McTominay", "McGinn", "Robertson", "Adams"],
    "Áustria": ["Sabitzer", "Laimer", "Gregoritsch", "Alaba"],
    "República Tcheca": ["Schick", "Soucek", "Hlozek"],
    "Turquia": ["Arda Güler", "Calhanoglu", "Yilmaz", "Bayindir"],
    "Bósnia": ["Dzeko", "Demirovic", "Pjanic"],
    "RD Congo": ["Wissa", "Bakambu", "Mbemba"],
    "Iraque": ["Aymen Hussein", "Ali Jasim", "Resan"],
    "Haiti": ["Nazón", "Pierrot", "Guerrier"],
    "Jordânia": ["Al-Taamari", "Olwan", "Al-Naimat"],
    "Noruega": ["Haaland", "Ødegaard", "Sørloth"],
    "Nova Zelândia": ["Wood", "Cacace", "Singh"],
    "Uzbequistão": ["Shomurodov", "Masharipov", "Fayzullaev"],
    "Argélia": ["Mahrez", "Bounedjah", "Aouar", "Bensebaini"],
    "Cabo Verde": ["Ryan Mendes", "Bebé", "Cabral"],
    "Curaçao": ["Bacuna", "Janga", "Anita"]
}



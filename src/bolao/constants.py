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

ACTIVE_PARTICIPANT_NAMES = ["Baruja", "Fantato", "Henrique O Terrível"]


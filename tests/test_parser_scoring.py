import pytest

from src.bolao.parser_ge import (
    detect_section,
    is_champion_heading,
    is_noise,
    parse_ge_knockout_text,
    split_match,
)
from src.bolao.models import Prediction
from src.bolao.scoring import ScoreConfig, rank_predictions
from src.bolao.validation import validate_prediction, has_blocking_errors


def sample_text(champion="França"):
    return f"""
Simulador Copa do Mundo 2026

Décima-sextas
Alemanha x Paraguai
França x Suécia

Oitavas
Alemanha x França

Quartas
França x Holanda

Semi
França x Espanha

Final
França x Inglaterra

Campeã
{champion}
"""


class TestParserGE:
    def test_detect_section_decima_sextas(self):
        assert detect_section("Décima-sextas") == "fase_32"
        assert detect_section("decima-sextas") == "fase_32"
        assert detect_section("16 avos") == "fase_32"
        assert detect_section("fase de 32") == "fase_32"

    def test_detect_section_oitavas(self):
        assert detect_section("Oitavas") == "oitavas"
        assert detect_section("oitavas de final") == "oitavas"

    def test_detect_section_quartas(self):
        assert detect_section("Quartas") == "quartas"
        assert detect_section("quartas de final") == "quartas"

    def test_detect_section_semi(self):
        assert detect_section("Semi") == "semifinais"
        assert detect_section("Semis") == "semifinais"
        assert detect_section("Semifinal") == "semifinais"

    def test_detect_section_final(self):
        assert detect_section("Final") == "final"

    def test_is_champion_heading(self):
        assert is_champion_heading("Campeã") is True
        assert is_champion_heading("Campeão") is True
        assert is_champion_heading("campea") is True
        assert is_champion_heading("Final") is False

    def test_is_noise(self):
        assert is_noise("Simulador Copa do Mundo 2026") is True
        assert is_noise("#ge.globoNaCopa") is True
        assert is_noise("ge.globo/simulador") is True
        assert is_noise("") is True
        assert is_noise("Alemanha x Brasil") is False

    def test_split_match(self):
        assert split_match("Alemanha x Brasil") == ("Alemanha", "Brasil")
        assert split_match("França X Espanha") == ("França", "Espanha")
        assert split_match("Brasil vs Argentina") == ("Brasil", "Argentina")
        assert split_match("não é um jogo") is None

    def test_parse_complete_knockout(self):
        knockout, champion, issues, meta = parse_ge_knockout_text(sample_text())
        assert champion == "França"
        assert len(knockout["fase_32"]) == 2
        assert len(knockout["oitavas"]) == 1
        assert len(knockout["quartas"]) == 1
        assert len(knockout["semifinais"]) == 1
        assert len(knockout["final"]) == 1

    def test_parser_infers_winners(self):
        knockout, champion, issues, meta = parse_ge_knockout_text(sample_text())
        assert champion == "França"
        assert knockout["final"][0].winner == "França"

    def test_parser_variations(self):
        text = """
Simulador Copa do Mundo 2026

Decima-sextas
Alemanha x Paraguai
França x Suécia

Oitavas
Alemanha x França

Quartas
França x Holanda

Semi
França x Espanha

Final
França x Inglaterra

Campeã
França
"""
        knockout, champion, _, _ = parse_ge_knockout_text(text)
        assert champion == "França"

    def test_parser_missing_champion(self):
        text = """
Décima-sextas
Alemanha x Paraguai

Oitavas
Alemanha x França
"""
        _, champion, issues, _ = parse_ge_knockout_text(text)
        assert champion is None
        assert any(i.message == "Campeã ausente." for i in issues)


class TestScoring:
    def test_ranking_basic(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, champ, _, _ = parse_ge_knockout_text(sample_text())
        official = Prediction(participant="Resultado", groups=groups, knockout=ko, champion=champ)
        pred = Prediction(participant="Cesar", groups=groups, knockout=ko, champion=champ)
        scores = rank_predictions([pred], official, ScoreConfig())
        assert scores[0].total > 0
        assert scores[0].champion_hit == 1

    def test_ranking_tiebreaker(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, champ, _, _ = parse_ge_knockout_text(sample_text())
        official = Prediction(participant="Resultado", groups=groups, knockout=ko, champion=champ)
        pred1 = Prediction(participant="Ana", groups=groups, knockout=ko, champion=champ)
        pred2 = Prediction(participant="Beto", groups=groups, knockout=ko, champion=champ)
        scores = rank_predictions([pred1, pred2], official, ScoreConfig())
        assert len(scores) == 2
        assert scores[0].total == scores[1].total

    def test_scoring_ponderado(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, champ, _, _ = parse_ge_knockout_text(sample_text())
        official = Prediction(participant="Resultado", groups=groups, knockout=ko, champion="França")
        pred = Prediction(
            participant="Participante",
            groups=groups,
            knockout=ko,
            champion="França"
        )
        config = ScoreConfig(mode="ponderado")
        scores = rank_predictions([pred], official, config)
        assert scores[0].total > 0
        assert scores[0].champion_hit == 1

    def test_scoring_uniforme(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, champ, _, _ = parse_ge_knockout_text(sample_text())
        official = Prediction(participant="Resultado", groups=groups, knockout=ko, champion="França")
        pred = Prediction(
            participant="Participante",
            groups=groups,
            knockout=ko,
            champion="França"
        )
        config = ScoreConfig(mode="uniforme", uniform_rules={"decision_points": 2, "champion_bonus": 5})
        scores = rank_predictions([pred], official, config)
        assert scores[0].total > 0


class TestValidation:
    def test_validate_prediction_valid(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, champ, _, _ = parse_ge_knockout_text(sample_text())
        pred = Prediction(participant="Teste", groups=groups, knockout=ko, champion="França")
        issues = validate_prediction(pred, strict=False)
        assert len(issues) == 0

    def test_validate_prediction_no_name(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, champ, _, _ = parse_ge_knockout_text(sample_text())
        pred = Prediction(participant="", groups=groups, knockout=ko, champion="França")
        issues = validate_prediction(pred, strict=False)
        assert any(i.message == "Informe o nome do participante." for i in issues)

    def test_validate_prediction_missing_champion(self):
        groups = {g: ["A", "B", "C", "D"] for g in "ABCDEFGHIJKL"}
        ko, _, _, _ = parse_ge_knockout_text(sample_text())
        pred = Prediction(participant="Teste", groups=groups, knockout=ko, champion=None)
        issues = validate_prediction(pred, strict=False)
        assert any("Campeã" in i.message for i in issues)

    def test_has_blocking_errors(self):
        from src.bolao.models import ParseIssue
        issues = [ParseIssue("error", "Erro crítico")]
        assert has_blocking_errors(issues) is True
        issues = [ParseIssue("warning", "Aviso")]
        assert has_blocking_errors(issues) is False


class TestOCRGroups:
    def test_merge_ocr_results_order(self):
        from src.bolao.ocr_groups import OCRResult, OCRField, merge_ocr_results

        result1 = OCRResult()
        result1.groups = {
            "A": [OCRField("México", 0.9), OCRField("África do Sul", 0.9), OCRField("Coreia do Sul", 0.9), OCRField("Rep. Tcheca", 0.9)],
            "B": [OCRField("Canadá", 0.9), OCRField("Bósnia", 0.9), OCRField("Catar", 0.9), OCRField("Suíça", 0.9)],
            "C": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "D": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "E": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "F": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "G": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "H": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "I": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "J": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "K": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "L": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
        }

        result2 = OCRResult()
        result2.groups = {
            "G": [OCRField("Bélgica", 0.9), OCRField("Egito", 0.9), OCRField("Irã", 0.9), OCRField("Nova Zelândia", 0.9)],
            "H": [OCRField("Espanha", 0.9), OCRField("Cabo Verde", 0.9), OCRField("Arábia Saudita", 0.9), OCRField("Uruguai", 0.9)],
            "I": [OCRField("França", 0.9), OCRField("Senegal", 0.9), OCRField("Iraque", 0.9), OCRField("Noruega", 0.9)],
            "J": [OCRField("Argentina", 0.9), OCRField("Argélia", 0.9), OCRField("Áustria", 0.9), OCRField("Jordânia", 0.9)],
            "K": [OCRField("Portugal", 0.9), OCRField("RD Congo", 0.9), OCRField("Uzbequistão", 0.9), OCRField("Colômbia", 0.9)],
            "L": [OCRField("Inglaterra", 0.9), OCRField("Croácia", 0.9), OCRField("Gana", 0.9), OCRField("Panamá", 0.9)],
            "A": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "B": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "C": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "D": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "E": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
            "F": [OCRField(None, 0), OCRField(None, 0), OCRField(None, 0), OCRField(None, 0)],
        }

        groups, meta = merge_ocr_results([result1, result2])
        assert groups["A"][0] == "México"
        assert groups["L"][0] == "Inglaterra"
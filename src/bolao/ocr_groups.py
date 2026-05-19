from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from .constants import GE_GROUP_ROW_ORDER, GROUPS, TEAM_ALIASES
from .utils import canonical_team, norm_text


@dataclass
class OCRField:
    value: str | None
    confidence: float
    source: str = "ocr"


@dataclass
class OCRResult:
    raw_text: str = ""
    groups: dict[str, list[OCRField]] = field(default_factory=lambda: {g: [OCRField(None, 0.0) for _ in range(4)] for g in GROUPS})
    best_thirds: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    available: bool = True
    engine: str = "ge-layout+tesseract-fallback"
    meta: dict[str, Any] = field(default_factory=dict)


# Cores do simulador do ge nas linhas selecionadas.
# 1º = roxo, 2º = vinho/rosa, 3º = ocre, 4º = cinza claro.
# O parser não depende do OCR para os grupos: ele lê a posição pela cor da linha
# e usa a ordem fixa dos times no card do ge.
POSITION_PALETTES = {
    1: np.array([112, 86, 183]),
    2: np.array([193, 75, 112]),
    3: np.array([209, 149, 72]),
    4: np.array([243, 243, 243]),
}


def _open_image(file_bytes: bytes | Image.Image) -> Image.Image:
    if isinstance(file_bytes, Image.Image):
        return file_bytes.convert("RGB")
    return Image.open(io.BytesIO(file_bytes)).convert("RGB")


def preprocess_image(file_bytes: bytes | Image.Image) -> Image.Image:
    img = _open_image(file_bytes)
    max_width = 2600
    min_width = 1500
    w, h = img.size
    if w < min_width:
        scale = min_width / max(w, 1)
        img = img.resize((int(w * scale), int(h * scale)))
    elif w > max_width:
        scale = max_width / w
        img = img.resize((int(w * scale), int(h * scale)))

    gray = ImageOps.grayscale(img)
    gray = ImageEnhance.Contrast(gray).enhance(1.8)
    gray = ImageEnhance.Sharpness(gray).enhance(1.6)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    return gray


def _try_tesseract(image: Image.Image) -> tuple[str, float, str | None]:
    try:
        import pytesseract
    except Exception as exc:
        return "", 0.0, f"pytesseract não está instalado no ambiente: {exc}"

    try:
        config = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(image, lang="por+eng", config=config)
        data = pytesseract.image_to_data(image, lang="por+eng", config=config, output_type=pytesseract.Output.DICT)
        confs = []
        for c in data.get("conf", []):
            try:
                val = float(c)
                if val >= 0:
                    confs.append(val)
            except Exception:
                pass
        avg = sum(confs) / len(confs) if confs else 0.0
        return text, avg, None
    except Exception as exc:
        return "", 0.0, (
            "Não consegui executar o Tesseract OCR. "
            "No Windows, instale o Tesseract. No Streamlit Cloud, confira o arquivo packages.txt. "
            f"Detalhe técnico: {exc}"
        )


def _find_separator_lines(img: Image.Image) -> list[int]:
    arr = np.asarray(img.convert("RGB"))
    h, w = arr.shape[:2]
    dark = ((arr[:, :, 0] < 80) & (arr[:, :, 1] < 80) & (arr[:, :, 2] < 80)).sum(axis=1)
    candidates = [y for y, count in enumerate(dark) if count > w * 0.50]
    clusters: list[list[int]] = []
    for y in candidates:
        if not clusters or y - clusters[-1][-1] > 2:
            clusters.append([y])
        else:
            clusters[-1].append(y)
    centers = [round(sum(c) / len(c)) for c in clusters]
    # Mantém linhas largas horizontais reais. Textos pequenos não passam do limiar.
    return centers[:2]


def _fallback_separator_lines(img: Image.Image) -> list[int]:
    # Prints com título "Grupos" no topo costumam ter a primeira linha por volta de 14% da altura.
    w, h = img.size
    if h >= 690:
        return [int(h * 0.137), int(h * 0.599)]
    return [int(h * 0.058), int(h * 0.562)]


def _classify_row_color(rgb: np.ndarray) -> tuple[int, float]:
    distances = {pos: float(np.linalg.norm(rgb.astype(float) - palette.astype(float))) for pos, palette in POSITION_PALETTES.items()}
    pos = min(distances, key=distances.get)
    dist = distances[pos]
    # Converte distância em confiança simples. Distâncias abaixo de 25 são praticamente exatas.
    confidence = max(0.45, min(0.99, 1.0 - (dist / 180.0)))
    return pos, confidence


def parse_ge_group_screenshot(img: Image.Image, expected_groups: list[str]) -> tuple[dict[str, list[OCRField]], list[str], dict[str, Any]]:
    groups = {g: [OCRField(None, 0.0) for _ in range(4)] for g in GROUPS}
    warnings: list[str] = []
    meta: dict[str, Any] = {"method": "ge_layout_color", "cells": []}

    expected = expected_groups or GROUPS
    if not expected:
        return groups, ["Nenhum grupo esperado foi informado para a imagem."], meta

    img = img.convert("RGB")
    arr = np.asarray(img)
    h, w = arr.shape[:2]
    lines = _find_separator_lines(img)
    if len(lines) < 2:
        lines = _fallback_separator_lines(img)
        warnings.append("Não localizei perfeitamente as linhas dos cards. Usei leitura geométrica aproximada; revise a conferência.")
    meta["separator_lines"] = lines
    block_h = max(1, lines[1] - lines[0])
    row_offset = 0.176 * block_h
    row_step = 0.132 * block_h
    row_half = max(7, int(row_step * 0.28))
    col_w = w / 3

    if len(expected) != 6:
        warnings.append(f"A imagem deveria conter 6 grupos, mas o sistema recebeu {len(expected)} grupos esperados.")

    for idx, group in enumerate(expected[:6]):
        if group not in GE_GROUP_ROW_ORDER:
            warnings.append(f"Grupo {group}: ordem visual do ge não configurada.")
            continue
        row_block = idx // 3
        col = idx % 3
        x0 = int(col * col_w)
        x1 = int((col + 1) * col_w)
        line_y = lines[row_block] if row_block < len(lines) else int(row_block * h / 2)
        teams_in_visual_order = GE_GROUP_ROW_ORDER[group]
        slots_by_position: dict[int, list[tuple[str, float, np.ndarray]]] = {1: [], 2: [], 3: [], 4: []}

        for team_idx, team in enumerate(teams_in_visual_order):
            # Centro da faixa colorida do time no card.
            cy = int(line_y + row_offset + team_idx * row_step + row_step / 2)
            y0 = max(0, cy - row_half)
            y1 = min(h, cy + row_half)
            # Evita bordas, flags e os círculos das opções à direita. A mediana torna o texto branco irrelevante.
            rx0 = max(x0 + int(col_w * 0.20), 0)
            rx1 = min(x0 + int(col_w * 0.67), w)
            if rx1 <= rx0 or y1 <= y0:
                warnings.append(f"Grupo {group}: não consegui amostrar a linha de {team}.")
                continue
            rect = arr[y0:y1, rx0:rx1, :]
            median_rgb = np.median(rect.reshape(-1, 3), axis=0)
            position, confidence = _classify_row_color(median_rgb)
            slots_by_position[position].append((team, confidence, median_rgb))
            meta["cells"].append({
                "grupo": group,
                "time": team,
                "linha": team_idx + 1,
                "rgb": [int(x) for x in median_rgb.tolist()],
                "posicao_detectada": position,
                "confianca": round(confidence, 3),
            })

        # Primeiro preenche as posições explícitas do simulador: 1º, 2º e 3º classificado.
        for position in range(1, 4):
            candidates = slots_by_position[position]
            if len(candidates) == 1:
                team, confidence, _ = candidates[0]
                groups[group][position - 1] = OCRField(team, confidence, "ge_layout_color")
            elif len(candidates) > 1:
                names = ", ".join(c[0] for c in candidates)
                warnings.append(f"Grupo {group}: mais de uma seleção parece marcada como {position}º lugar: {names}. Revise manualmente.")
                team, _, _ = candidates[0]
                groups[group][position - 1] = OCRField(team, 0.35, "ge_layout_conflict")

        # Linhas cinzas são os times restantes. No ge, quando o 3º do grupo não
        # está entre os melhores terceiros, ficam duas linhas cinzas; nesses casos
        # preenchemos 3º e 4º pela ordem visual para não gerar grupos vazios.
        grey_candidates = slots_by_position[4]
        missing_positions = [pos for pos in range(1, 5) if not groups[group][pos - 1].value]
        for pos, candidate in zip(missing_positions, grey_candidates):
            team, confidence, _ = candidate
            source = "ge_layout_color" if pos == 4 and len(grey_candidates) == 1 else "ge_layout_remaining"
            adjusted_conf = confidence if source == "ge_layout_color" else min(confidence, 0.58)
            groups[group][pos - 1] = OCRField(team, adjusted_conf, source)

        if len(grey_candidates) > len(missing_positions):
            names = ", ".join(c[0] for c in grey_candidates[len(missing_positions):])
            warnings.append(f"Grupo {group}: sobraram linhas cinzas sem posição definida: {names}. Revise manualmente.")

        if len(grey_candidates) >= 2 and 3 in missing_positions:
            meta.setdefault("notes", []).append(
                f"Grupo {group}: 3º/4º preenchidos pela ordem visual do card porque o ge não marcou terceiro classificado."
            )

        for position in range(1, 5):
            if not groups[group][position - 1].value:
                warnings.append(f"Grupo {group}: não detectei seleção para {position}º lugar.")

        values = [field.value for field in groups[group]]
        if len([v for v in values if v]) == 4 and len(set(values)) != 4:
            warnings.append(f"Grupo {group}: seleção repetida após a leitura. Revise manualmente.")

    return groups, warnings, meta


def _find_team_mentions(line: str) -> list[str]:
    clean_line = norm_text(line)
    found: list[str] = []
    for canonical, aliases in TEAM_ALIASES.items():
        if canonical in found:
            continue
        for alias in aliases + [canonical]:
            alias_norm = norm_text(alias)
            if not alias_norm:
                continue
            if f" {alias_norm} " in f" {clean_line} " or alias_norm in clean_line:
                found.append(canonical)
                break
    return found


def parse_groups_from_ocr_text(text: str, expected_groups: list[str] | None = None) -> tuple[dict[str, list[OCRField]], list[str]]:
    expected = expected_groups or GROUPS
    groups = {g: [OCRField(None, 0.0) for _ in range(4)] for g in GROUPS}
    warnings: list[str] = []

    current: str | None = None
    lines = [line.strip() for line in (text or "").replace("\r", "\n").split("\n") if line.strip()]
    for line in lines:
        clean = norm_text(line)
        for g in expected:
            if f"grupo {g.lower()}" in clean or f"group {g.lower()}" in clean or clean == g.lower():
                current = g
                break

        mentions = _find_team_mentions(line)
        if current and mentions:
            for team in mentions:
                team = canonical_team(team)
                slots = groups[current]
                current_values = [x.value for x in slots]
                if team in current_values:
                    continue
                try:
                    idx = current_values.index(None)
                except ValueError:
                    continue
                slots[idx] = OCRField(team, 0.65, "ocr_text_fallback")

    detected_count = sum(1 for g in expected for s in groups[g] if s.value)
    if detected_count < 8:
        all_mentions: list[str] = []
        for line in lines:
            for team in _find_team_mentions(line):
                team = canonical_team(team)
                if team and team not in all_mentions:
                    all_mentions.append(team)
        if len(all_mentions) >= 4:
            cursor = 0
            for g in expected:
                for pos in range(4):
                    if cursor < len(all_mentions) and not groups[g][pos].value:
                        groups[g][pos] = OCRField(all_mentions[cursor], 0.35, "ocr_text_fallback")
                    cursor += 1

    for g in expected:
        values = [s.value for s in groups[g]]
        if any(values) and not all(values):
            warnings.append(f"Grupo {g}: OCR textual incompleto. Revise manualmente.")
        if not any(values):
            warnings.append(f"Grupo {g}: nenhum time detectado. Preencha na conferência.")
    return groups, warnings


def run_group_ocr(file_bytes: bytes, expected_groups: list[str] | None = None) -> OCRResult:
    result = OCRResult()
    expected = expected_groups or GROUPS
    try:
        img = _open_image(file_bytes)
    except Exception as exc:
        result.available = False
        result.warnings.append(f"Não consegui abrir a imagem: {exc}")
        return result

    layout_groups, layout_warnings, layout_meta = parse_ge_group_screenshot(img, expected)
    layout_detected = sum(1 for g in expected for f in layout_groups[g] if f.value)

    # O Tesseract fica como camada auxiliar: útil para debug e fallback em prints fora do padrão.
    raw_tesseract = ""
    avg_conf = 0.0
    tess_error = None
    try:
        text_img = preprocess_image(img)
        raw_tesseract, avg_conf, tess_error = _try_tesseract(text_img)
    except Exception as exc:
        tess_error = str(exc)

    result.meta = {"layout": layout_meta, "tesseract_confidence": avg_conf}
    result.raw_text = (
        "[Extração por layout do ge]\n"
        + "\n".join(
            f"Grupo {cell['grupo']} · {cell['time']} → {cell['posicao_detectada']}º · RGB {cell['rgb']} · conf. {cell['confianca']}"
            for cell in layout_meta.get("cells", [])
        )
        + "\n\n[OCR textual auxiliar]\n"
        + (raw_tesseract or "")
    )

    if layout_detected >= max(4, len(expected) * 3):
        result.groups = layout_groups
        result.warnings.extend(layout_warnings)
        # Não transforma ausência do Tesseract em erro quando a leitura por layout funcionou.
        if tess_error:
            result.meta["tesseract_note"] = tess_error
        return result

    # Fallback antigo para imagens fora do padrão do simulador.
    text_groups, text_warnings = parse_groups_from_ocr_text(raw_tesseract, expected)
    text_detected = sum(1 for g in expected for f in text_groups[g] if f.value)
    if text_detected > layout_detected:
        result.groups = text_groups
        result.warnings.extend(text_warnings)
        result.warnings.append("Usei fallback por OCR textual porque a leitura geométrica não conseguiu reconhecer o print como card do ge.")
    else:
        result.groups = layout_groups
        result.warnings.extend(layout_warnings)
        result.warnings.append("A leitura dos grupos ficou incompleta. Revise e complete manualmente antes de salvar.")
    if tess_error and not raw_tesseract:
        result.warnings.append(tess_error)
    return result


def merge_ocr_results(results: list[OCRResult]) -> tuple[dict[str, list[str | None]], dict[str, Any]]:
    groups: dict[str, list[str | None]] = {g: [None, None, None, None] for g in GROUPS}
    confidence: dict[str, list[float]] = {g: [0.0, 0.0, 0.0, 0.0] for g in GROUPS}
    sources: dict[str, list[str]] = {g: ["", "", "", ""] for g in GROUPS}
    warnings: list[str] = []
    raw_texts: list[str] = []
    layouts: list[dict[str, Any]] = []

    for result in results:
        raw_texts.append(result.raw_text)
        warnings.extend(result.warnings)
        if result.meta.get("layout"):
            layouts.append(result.meta["layout"])
        for g, fields in result.groups.items():
            for idx, field in enumerate(fields[:4]):
                if field.value and not groups[g][idx]:
                    groups[g][idx] = field.value
                    confidence[g][idx] = field.confidence
                    sources[g][idx] = field.source

    meta = {
        "confidence": confidence,
        "sources": sources,
        "warnings": warnings,
        "raw_ocr_text": "\n\n--- OCR ---\n\n".join(raw_texts),
        "layouts": layouts,
    }
    return groups, meta

from __future__ import annotations

import streamlit as st
import pandas as pd
from datetime import datetime, date
from .ui_components import render_page_header, render_responsive_table
from .storage import (
    load_matches, load_artilheiro_palpites_dia, save_artilheiro_palpite_dia,
    load_artilheiro_palpites_rodada, save_artilheiro_palpite_rodada,
    load_brasil_palpites_classicos, save_brasil_palpite_classico,
    load_live_predictions, load_config,
)
from .utils import normalize_participant_key, now_iso
from .models import LiveMatch

import sys
try:
    from squad_lists_2026 import SQUAD_LISTS_2026
except ImportError:
    import os
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from squad_lists_2026 import SQUAD_LISTS_2026


def _get_upcoming_dates(matches: list[LiveMatch], min_date: str | None = None) -> list[str]:
    today_str = date.today().isoformat()
    dates = sorted(set(
        m.starts_at.split("T")[0] for m in matches
        if m.starts_at and m.starts_at.split("T")[0] >= today_str
    ))
    if min_date and min_date in dates:
        idx = dates.index(min_date)
        dates = dates[idx:]
    return dates


def _get_rounds_from_today(matches: list[LiveMatch]) -> list[str]:
    today_str = date.today().isoformat()
    seen = set()
    rounds = []
    for m in sorted(matches, key=lambda x: x.starts_at or ""):
        if m.starts_at and m.starts_at.split("T")[0] >= today_str:
            r = m.round_label
            if r not in seen:
                seen.add(r)
                rounds.append(r)
    return rounds


def _team_picker(label: str, key: str, default_team: str = "") -> tuple[str, str]:
    teams = sorted(SQUAD_LISTS_2026.keys(), key=lambda t: t.lower())
    team_idx = 0
    if default_team and default_team in teams:
        team_idx = teams.index(default_team)
    sel_team = st.selectbox(
        f"{label} — Selecionar Time",
        teams,
        index=team_idx,
        key=f"{key}_team",
    )
    players = SQUAD_LISTS_2026.get(sel_team, [])
    if not players:
        return sel_team, ""
    player_names = [p["nome"] for p in players]
    sel_player = st.selectbox(
        f"{label} — Escolher Jogador",
        [""] + player_names,
        key=f"{key}_player",
    )
    return sel_team, sel_player


def _render_player_select_team_first(
    label: str,
    key: str,
    current_team: str = "",
    current_player: str = "",
) -> tuple[str, str]:
    teams = sorted(SQUAD_LISTS_2026.keys(), key=lambda t: t.lower())
    team_idx = 0
    if current_team and current_team in teams:
        team_idx = teams.index(current_team)

    col_t, col_p = st.columns([1, 2])
    with col_t:
        sel_team = st.selectbox(
            f"{label} — Time",
            teams,
            index=team_idx,
            key=f"{key}_art_team",
            label_visibility="collapsed",
        )
    players = SQUAD_LISTS_2026.get(sel_team, [])
    player_names = [p["nome"] for p in players]
    p_idx = 0
    if current_player and current_player in player_names:
        p_idx = player_names.index(current_player) + 1
    with col_p:
        sel_player = st.selectbox(
            f"{label} — Jogador",
            [""] + player_names,
            index=p_idx,
            key=f"{key}_art_player",
            label_visibility="collapsed",
        )
    return sel_team, sel_player


def render_page_artilheiro() -> None:
    render_page_header(
        "Artilheiro",
        "Palpites de Artilheiro",
        "Quem vai balançar as redes? Palpite o artilheiro do dia, da rodada e da copa.",
        "⚽",
    )

    matches = load_matches()
    config = load_config()
    pkey = normalize_participant_key(st.session_state.get("live_user_name", ""))
    display_name = st.session_state.get("live_user_name", "")

    tabs = st.tabs([
        "📅 Artilheiro do Dia",
        "📆 Artilheiro da Rodada",
        "🏆 Artilheiro da Copa",
    ])

    # ── Tab 1: Artilheiro do Dia ──────────────────────────────────────────
    with tabs[0]:
        st.markdown("#### ⚽ Quem vai ser o artilheiro de cada dia?")
        st.caption("Selecione um dia e escolha o jogador que mais fará gols nas partidas daquele dia.")

        upcoming = _get_upcoming_dates(matches)
        if not upcoming:
            st.info("Nenhum jogo futuro agendado.")
        else:
            sel_date = st.selectbox("Escolha o dia", upcoming, key="art_dia_date")
            day_matches = [
                m for m in matches
                if m.starts_at and m.starts_at.startswith(sel_date)
            ]
            if day_matches:
                st.markdown(f"**Jogos de {sel_date}:**")
                for m in day_matches:
                    st.markdown(f"- {m.home_team} x {m.away_team} ({m.round_label})")
            st.markdown("---")

            all_dia = load_artilheiro_palpites_dia()
            current_dia = next(
                (p for p in all_dia if p["participante_nome"] == display_name and p["data"] == sel_date),
                None,
            )
            cur_team = current_dia.get("selecao", "") if current_dia else ""
            cur_player = current_dia.get("jogador", "") if current_dia else ""

            team, player = _render_player_select_team_first(
                "Artilheiro do Dia", f"art_dia_{sel_date}",
                cur_team, cur_player,
            )

            st.markdown("---")
            if st.button("💾 Salvar Artilheiro do Dia", type="primary", key="btn_save_art_dia", width="stretch"):
                if not player:
                    st.error("Selecione um jogador.")
                elif not display_name:
                    st.error("Você precisa estar logado para salvar.")
                else:
                    save_artilheiro_palpite_dia({
                        "participante_nome": display_name,
                        "data": sel_date,
                        "jogador": player,
                        "selecao": team,
                        "atualizado_em": now_iso(),
                    })
                    st.success(f"✅ Artilheiro de {sel_date}: {player} ({team}) salvo!")
                    st.rerun()

            # Show all predictions for this day
            st.markdown("---")
            st.markdown("##### 👥 Palpites de todos para este dia")
            day_preds = [p for p in all_dia if p["data"] == sel_date]
            if day_preds:
                df = pd.DataFrame(day_preds)
                for col in ["atualizado_em"]:
                    if col in df.columns:
                        df.drop(columns=[col], inplace=True)
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.caption("Ninguém palpitou ainda para este dia.")

    # ── Tab 2: Artilheiro da Rodada ───────────────────────────────────────
    with tabs[1]:
        st.markdown("#### 📆 Quem vai ser o artilheiro de cada rodada?")
        st.caption("Escolha a rodada e o jogador que mais fará gols naquela rodada.")

        rounds = _get_rounds_from_today(matches)
        if not rounds:
            st.info("Nenhuma rodada futura encontrada.")
        else:
            sel_round = st.selectbox("Escolha a rodada", rounds, key="art_rodada_sel")

            round_matches = [
                m for m in matches
                if m.round_label == sel_round
                and m.starts_at
                and m.starts_at.split("T")[0] >= date.today().isoformat()
            ]
            if round_matches:
                st.markdown(f"**Jogos da {sel_round}:**")
                for m in round_matches:
                    st.markdown(f"- {m.home_team} x {m.away_team} ({m.group or '—'})")
            st.markdown("---")

            all_rod = load_artilheiro_palpites_rodada()
            current_rod = next(
                (p for p in all_rod if p["participante_nome"] == display_name and p["rodada"] == sel_round),
                None,
            )
            cur_rteam = current_rod.get("selecao", "") if current_rod else ""
            cur_rplayer = current_rod.get("jogador", "") if current_rod else ""

            rteam, rplayer = _render_player_select_team_first(
                "Artilheiro da Rodada", f"art_rod_{sel_round}",
                cur_rteam, cur_rplayer,
            )

            st.markdown("---")
            if st.button("💾 Salvar Artilheiro da Rodada", type="primary", key="btn_save_art_rod", width="stretch"):
                if not rplayer:
                    st.error("Selecione um jogador.")
                elif not display_name:
                    st.error("Você precisa estar logado para salvar.")
                else:
                    save_artilheiro_palpite_rodada({
                        "participante_nome": display_name,
                        "rodada": sel_round,
                        "jogador": rplayer,
                        "selecao": rteam,
                        "atualizado_em": now_iso(),
                    })
                    st.success(f"✅ Artilheiro da {sel_round}: {rplayer} ({rteam}) salvo!")
                    st.rerun()

            st.markdown("---")
            st.markdown("##### 👥 Palpites de todos para esta rodada")
            rod_preds = [p for p in all_rod if p["rodada"] == sel_round]
            if rod_preds:
                df = pd.DataFrame(rod_preds)
                for col in ["atualizado_em"]:
                    if col in df.columns:
                        df.drop(columns=[col], inplace=True)
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.caption("Ninguém palpitou ainda para esta rodada.")

    # ── Tab 3: Artilheiro da Copa ─────────────────────────────────────────
    with tabs[2]:
        st.markdown("#### 🏆 Quem vai ser o artilheiro da Copa?")
        st.caption("Palpite o artilheiro geral do torneio (pode ser atualizado a qualquer momento).")

        classic_all = load_brasil_palpites_classicos()
        current_classic = next(
            (p for p in classic_all if normalize_participant_key(p.get("participante_nome", "")) == pkey),
            None,
        )
        cur_cteam = ""
        cur_cplayer = current_classic.get("artilheiro_geral_copa", "") if current_classic else ""
        if cur_cplayer:
            for t, ps in SQUAD_LISTS_2026.items():
                if any(p["nome"] == cur_cplayer for p in ps):
                    cur_cteam = t
                    break

        cteam, cplayer = _render_player_select_team_first(
            "Artilheiro da Copa", "art_copa",
            cur_cteam, cur_cplayer,
        )

        st.markdown("---")
        if st.button("💾 Salvar Artilheiro da Copa", type="primary", key="btn_save_art_copa", width="stretch"):
            if not cplayer:
                st.error("Selecione um jogador.")
            elif not display_name:
                st.error("Você precisa estar logado para salvar.")
            else:
                palpite = current_classic or {"participante_nome": display_name}
                palpite["artilheiro_geral_copa"] = cplayer
                if "participante_nome" not in palpite:
                    palpite["participante_nome"] = display_name
                save_brasil_palpite_classico(palpite)
                st.success(f"✅ Artilheiro da Copa: {cplayer} ({cteam}) salvo!")
                st.rerun()

        st.markdown("---")
        st.markdown("##### 👥 Palpites de todos para Artilheiro da Copa")
        copa_preds = [p for p in classic_all if p.get("artilheiro_geral_copa")]
        if copa_preds:
            rows = []
            for p in copa_preds:
                name = p.get("participante_nome", "?")
                player = p.get("artilheiro_geral_copa", "—")
                team = ""
                for t, ps in SQUAD_LISTS_2026.items():
                    if any(pl["nome"] == player for pl in ps):
                        team = t
                        break
                rows.append({"Participante": name, "Jogador": player, "Seleção": team})
            render_responsive_table(
                pd.DataFrame(rows),
                lambda r: st.markdown(
                    f"""<div class="card" style="margin-bottom:8px;padding:12px;">
                        <b>{r['Participante']}</b> → ⚽ {r['Jogador']} ({r['Seleção']})
                    </div>""",
                    unsafe_allow_html=True,
                ),
                "art_copa_table",
            )
        else:
            st.caption("Ninguém palpitou ainda no artilheiro da copa.")

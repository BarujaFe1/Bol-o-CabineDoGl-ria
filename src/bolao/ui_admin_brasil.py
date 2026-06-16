import streamlit as st
import os
import urllib.parse
from collections import Counter
from .constants import ELENCO_BRASIL_2026
from .storage import (
    load_config,
    save_config,
    load_matches,
    load_brasil_palpites_goleadores,
    load_brasil_resultados_goleadores,
    save_brasil_resultado_goleadores,
    recalcular_pontos_modulo_brasil,
)
from .utils import foto_jogador, avatar_url
from .navigation import navigate_to

def admin_selecao_brasileira() -> None:
    if st.button("⬅️ Voltar ao Painel Admin", key="back_to_dashboard_brasil_admin", width="stretch"):
        navigate_to("Dashboard")
    
    st.markdown("## 🇧🇷 Painel de Controle da Seleção Brasileira")
    st.caption("Gerencie o elenco (suspensões/fotos) e registre os resultados oficiais para pontuar o Módulo Brasil.")
    
    tab_elenco, tab_goleadores = st.tabs([
        "🇧🇷 Elenco e Status",
        "⚽ Goleadores Reais por Jogo"
    ])
    
    config = load_config()
    suspended_players = config.get("suspended_players", [])
    
    with tab_elenco:
        st.subheader("Elenco de Jogadores")
        st.caption("Marque jogadores como suspensos/lesionados para desativá-los dos palpites, ou faça upload de fotos reais.")
        
        # Filter by position
        if "admin_active_squad_filter" not in st.session_state:
            st.session_state["admin_active_squad_filter"] = "Todos"
            
        c_sq_filt = st.columns(5)
        positions = ["Todos", "GOL", "DEF", "MEI", "ATA"]
        emojis = {"Todos": "🌍", "GOL": "🧤", "DEF": "🛡️", "MEI": "⚙️", "ATA": "⚡"}
        
        for c_idx, pos in enumerate(positions):
            with c_sq_filt[c_idx]:
                if st.button(f"{emojis[pos]} {pos}", key=f"btn_sq_filt_adm_{pos}", type="primary" if st.session_state["admin_active_squad_filter"] == pos else "secondary", width="stretch"):
                    st.session_state["admin_active_squad_filter"] = pos
                    st.rerun()
                    
        p_filtered = [p for p in ELENCO_BRASIL_2026 if st.session_state["admin_active_squad_filter"] == "Todos" or p["posicao"] == st.session_state["admin_active_squad_filter"]]
        
        for p in p_filtered:
            is_susp = p["nome"] in suspended_players
            p_foto = foto_jogador(p["camisa"], p["nome"])
            
            with st.container(border=True):
                col_foto, col_details, col_status, col_upload = st.columns([1, 2, 2, 3])
                
                with col_foto:
                    st.image(p_foto, width=70)
                    
                with col_details:
                    st.markdown(f"#### #{p['camisa']} {p['nome']}")
                    st.markdown(f"**Posição:** {p['posicao']}")
                    
                with col_status:
                    # Suspend toggle
                    toggle_label = "🔴 Suspenso" if is_susp else "🟢 Ativo"
                    is_checked = st.checkbox(f"Suspender #{p['camisa']}", value=is_susp, key=f"susp_chk_{p['camisa']}")
                    if is_checked != is_susp:
                        if is_checked:
                            if p["nome"] not in suspended_players:
                                suspended_players.append(p["nome"])
                        else:
                            if p["nome"] in suspended_players:
                                suspended_players.remove(p["nome"])
                        config["suspended_players"] = suspended_players
                        save_config(config)
                        st.toast(f"Status de {p['nome']} atualizado.")
                        st.rerun()
                        
                with col_upload:
                    uploaded_file = st.file_uploader("Fazer upload de foto (.jpg)", type=["jpg", "jpeg"], key=f"uploader_{p['camisa']}")
                    if uploaded_file:
                        os.makedirs("assets/players", exist_ok=True)
                        dest_path = f"assets/players/camisa_{p['camisa']:02d}.jpg"
                        with open(dest_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        st.success(f"Foto de {p['nome']} salva!")
                        st.rerun()
                        
    with tab_goleadores:
        st.subheader("Registrar Goleadores e Assistentes Reais")
        
        matches = load_matches()
        br_matches = [m for m in matches if "Brasil" in m.home_team or "Brasil" in m.away_team]
        
        if not br_matches:
            st.info("Nenhum jogo do Brasil cadastrado na agenda.")
            return
            
        br_matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))
        
        jogo_selecionado = st.selectbox(
            "Selecione o jogo do Brasil",
            options=br_matches,
            format_func=lambda j: f"{j.home_team} {j.official_home_goals if j.official_home_goals is not None else ''} x {j.official_away_goals if j.official_away_goals is not None else ''} {j.away_team} — Rodada {j.round_label}"
        )
        
        if jogo_selecionado:
            m_id = jogo_selecionado.match_id
            
            # Load existing
            resultados = load_brasil_resultados_goleadores()
            saved_res = resultados.get(m_id, {})
            saved_goleadores = saved_res.get("goleadores_reais", [])
            saved_assistentes = saved_res.get("assistentes_reais", [])
            saved_first_goal = saved_res.get("primeiro_gol_copa", None)
            
            st.markdown("##### ⚽ Goleadores Reais do Brasil")
            st.caption("Defina a quantidade de gols marcados por cada jogador neste jogo.")
            
            goleadores_reais = []
            with st.expander("Expandir Elenco para Goleadores", expanded=False):
                cols_g = st.columns(4)
                for idx, jogador in enumerate(ELENCO_BRASIL_2026):
                    with cols_g[idx % 4]:
                        val_g = st.number_input(
                            f"{jogador['nome']} (#{jogador['camisa']})",
                            min_value=0, max_value=5,
                            value=saved_goleadores.count(jogador["nome"]),
                            step=1,
                            key=f"gol_real_{m_id}_{jogador['camisa']}"
                        )
                        if val_g > 0:
                            goleadores_reais.extend([jogador["nome"]] * val_g)
                            
            st.markdown("##### 🅰️ Assistentes Reais do Brasil")
            st.caption("Defina a quantidade de assistências feitas por cada jogador neste jogo.")
            
            assistentes_reais = []
            with st.expander("Expandir Elenco para Assistentes", expanded=False):
                cols_a = st.columns(4)
                for idx, jogador in enumerate(ELENCO_BRASIL_2026):
                    with cols_a[idx % 4]:
                        val_a = st.number_input(
                            f"{jogador['nome']} (#{jogador['camisa']})",
                            min_value=0, max_value=5,
                            value=saved_assistentes.count(jogador["nome"]),
                            step=1,
                            key=f"assist_real_{m_id}_{jogador['camisa']}"
                        )
                        if val_a > 0:
                            assistentes_reais.extend([jogador["nome"]] * val_a)
            
            st.markdown("##### 🥇 Primeiro Gol do Brasil na Copa")
            primeiro_gol_copa = st.checkbox(
                "🥇 Este jogo contém o 1º gol do Brasil na Copa 2026",
                value=saved_first_goal is not None
            )
            
            primeiro_goleador = None
            if primeiro_gol_copa:
                all_choices = sorted(list(set(goleadores_reais + [saved_first_goal] if saved_first_goal else goleadores_reais)))
                if not all_choices:
                    st.warning("Selecione pelo menos um goleador acima para definir o primeiro gol.")
                else:
                    sel_idx = 0
                    if saved_first_goal in all_choices:
                        sel_idx = all_choices.index(saved_first_goal)
                    primeiro_goleador = st.selectbox(
                        "Quem fez o 1º gol do Brasil na Copa?",
                        options=all_choices,
                        index=sel_idx
                    )
            
            st.markdown("---")
            if st.button("💾 Salvar Goleadores Reais e Recalcular Pontos", type="primary", width="stretch"):
                resultado_final = {
                    "jogo_id": m_id,
                    "goleadores_reais": goleadores_reais,
                    "assistentes_reais": assistentes_reais,
                    "primeiro_gol_copa": primeiro_goleador if primeiro_gol_copa else None,
                    "encerrado": True
                }
                save_brasil_resultado_goleadores(m_id, resultado_final)
                recalcular_pontos_modulo_brasil(m_id)
                st.success("Goleadores reais salvos! Pontuação do Módulo Brasil recalculada com sucesso.")
                st.rerun()

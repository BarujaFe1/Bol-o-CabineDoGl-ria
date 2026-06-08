import os
import random
import re
import pandas as pd
import streamlit as st

from .worldcup_2026_data import TEAMS, GROUPS_TEAMS, GROUP_MATCHES, BRACKET_SLOTS
from .simulator_models import GroupMatch, GroupStanding
from .simulator_engine import (
    calculate_group_standings,
    get_best_third_placed_teams,
    build_initial_bracket_slots,
    propagate_winner,
    serialize_slots_to_prediction,
    deserialize_prediction_to_slots,
    MAP_FASE_32,
    MAP_OITAVAS,
    MAP_QUARTAS,
    MAP_SEMIFINAIS,
    MAP_FINAL
)
from .models import Prediction

def get_team_badge_path(team_id: str) -> str | None:
    tinfo = TEAMS.get(team_id)
    if not tinfo:
        return None
    badge_rel = tinfo.get("badge")
    if badge_rel:
        clean_path = badge_rel.replace("./", "").replace("/", os.sep)
        # Find project root directory relative to this file (src/bolao/ui_simulator.py)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        abs_path = os.path.join(project_root, clean_path)
        if os.path.exists(abs_path):
            return abs_path
    return None

def init_simulator_state(prediction: Prediction, force_reset: bool = False):
    if "simulator" not in st.session_state or force_reset:
        # Load from prediction if available
        saved_matches = prediction.meta.get("group_matches", {})
        
        # Initialize group matches
        group_matches = {}
        for gm in GROUP_MATCHES:
            m_id = gm["id"]
            if m_id in saved_matches:
                score = saved_matches[m_id]
                group_matches[m_id] = [score[0], score[1]]
            else:
                group_matches[m_id] = [None, None]
                
        # Initialize standings and slots
        st.session_state["simulator"] = {
            "group_matches": group_matches,
            "slots": {},  # Will be populated
            "initialized": True
        }
        
        state = st.session_state["simulator"]
        
        # Load saved slots if available
        saved_slots = prediction.meta.get("slots", {})
        if saved_slots:
            slots = {}
            for k, v in saved_slots.items():
                try:
                    slots[int(k)] = v
                except ValueError:
                    slots[k] = v
            state["slots"] = slots
        else:
            # If group matches are complete, attempt to deserialize the prediction knockout stages
            unplayed = [m_id for m_id in group_matches if group_matches[m_id][0] is None or group_matches[m_id][1] is None]
            if not unplayed:
                try:
                    standings = recalculate_all_standings(state)
                    best_thirds_list = get_best_third_placed_teams(standings)[:8]
                    best_thirds_groups = []
                    for stg in best_thirds_list:
                        g_letter = next(g for g, t_ids in GROUPS_TEAMS.items() if stg.team_id in t_ids)
                        best_thirds_groups.append(g_letter)
                    slots = deserialize_prediction_to_slots(prediction, standings, best_thirds_groups)
                    state["slots"] = slots
                except Exception:
                    pass

def render_simulator(prediction: Prediction, is_admin: bool = False) -> Prediction | None:
    init_simulator_state(prediction)
    state = st.session_state["simulator"]
    
    # Global Controls
    st.markdown("### 🎛️ Controles do Simulador")
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        if st.button("🔮 Preencher teste automaticamente", help="Use o preenchimento automático apenas para testar o simulador. Para participar de verdade, preencha seus próprios placares.", use_container_width=True):
            # Fill group stage matches
            for gm in GROUP_MATCHES:
                # Random realistic football score
                h = random.choice([0, 1, 2, 3, 4])
                a = random.choice([0, 1, 2, 3])
                # Weights
                if random.random() < 0.2:
                    h = a = random.choice([0, 1, 2])
                state["group_matches"][gm["id"]] = [h, a]
            
            # Recalculate standings and slots
            standings = recalculate_all_standings(state)
            best_thirds = [stg.team_id for stg in get_best_third_placed_teams(standings)[:8]]
            best_thirds_groups = []
            for tid in best_thirds:
                g_letter = next(g for g, t_ids in GROUPS_TEAMS.items() if tid in t_ids)
                best_thirds_groups.append(g_letter)
                
            state["slots"] = build_initial_bracket_slots(standings, best_thirds_groups)
            
            # Simulate knockout randomly
            simulate_knockout_randomly(state["slots"])
            st.toast("Simulação aleatória gerada com sucesso!")
            st.rerun()
            
    with col_c2:
        if st.button("🧹 Limpar simulador", use_container_width=True):
            # Reset all
            for gm in GROUP_MATCHES:
                state["group_matches"][gm["id"]] = [None, None]
            state["slots"] = {i: None for i in range(63)}
            st.toast("Simulador limpo.")
            st.rerun()
            
    with col_c3:
        if st.button("🔄 Atualizar classificação", use_container_width=True):
            recalculate_all_standings(state)
            st.toast("Classificação atualizada!")
            st.rerun()

    # Step navigation tabs
    step_tabs = st.tabs(["1. Fase de grupos", "2. Classificados", "3. Mata-mata", "4. Revisão e envio"])
    with step_tabs[0]:
        st.markdown("### 🏟️ Simule os jogos dos grupos")
        st.caption("Preencha os placares dos jogos. A tabela do grupo é atualizada automaticamente conforme os resultados informados.")
        
        group_selector_tabs = st.tabs([f"Grupo {g}" for g in GROUPS_TEAMS.keys()])
        
        for g_idx, g_letter in enumerate(GROUPS_TEAMS.keys()):
            with group_selector_tabs[g_idx]:
                st.markdown(f"#### Grupo {g_letter} - Simulação de Jogos")
                
                # Show matches for this group
                g_matches = [gm for gm in GROUP_MATCHES if gm["group"] == g_letter]
                
                col_m1, col_m2 = st.columns(2)
                for idx, gm in enumerate(g_matches):
                    # Alternate columns
                    col = col_m1 if idx % 2 == 0 else col_m2
                    with col:
                        # Match Container Box
                        if gm.get("stadium"):
                            st.markdown(f"**Rodada {gm['round']}** · *{gm['stadium']}*")
                        else:
                            st.markdown(f"**Rodada {gm['round']}**")
                        h_id, a_id = gm["home_id"], gm["away_id"]
                        h_name, a_name = TEAMS[h_id]["name"], TEAMS[a_id]["name"]
                        h_badge = get_team_badge_path(h_id)
                        a_badge = get_team_badge_path(a_id)
                        
                        sub_c1, sub_c2, sub_c3, sub_c4, sub_c5 = st.columns([3, 2, 1, 2, 3])
                        
                        with sub_c1:
                            if h_badge:
                                st.image(h_badge, width=32)
                            st.markdown(f"<div style='text-align: right;'><b>{h_name}</b></div>", unsafe_allow_html=True)
                            
                        with sub_c2:
                            val_h = state["group_matches"][gm["id"]][0]
                            new_h = st.number_input(
                                "Gols Home",
                                min_value=0,
                                max_value=9,
                                value=val_h,
                                step=1,
                                key=f"score_h_{gm['id']}",
                                label_visibility="collapsed"
                            )
                            
                        with sub_c3:
                            st.markdown("<div style='text-align: center; line-height: 40px;'>x</div>", unsafe_allow_html=True)
                            
                        with sub_c4:
                            val_a = state["group_matches"][gm["id"]][1]
                            new_a = st.number_input(
                                "Gols Away",
                                min_value=0,
                                max_value=9,
                                value=val_a,
                                step=1,
                                key=f"score_a_{gm['id']}",
                                label_visibility="collapsed"
                            )
                            
                        with sub_c5:
                            if a_badge:
                                st.image(a_badge, width=32)
                            st.markdown(f"<div><b>{a_name}</b></div>", unsafe_allow_html=True)
                            
                        # Save if score changed
                        if new_h != val_h or new_a != val_a:
                            state["group_matches"][gm["id"]] = [new_h, new_a]
                            
                st.markdown("---")
                st.markdown("#### Classificação do Grupo")
                
                # Check if group is completely unplayed
                group_unplayed = [gm["id"] for gm in g_matches if state["group_matches"][gm["id"]][0] is None or state["group_matches"][gm["id"]][1] is None]
                if len(group_unplayed) == len(g_matches):
                    st.info("ℹ️ Preencha os jogos deste grupo para calcular a classificação.")
                
                # Calculate current standing
                match_objs = []
                for m in GROUP_MATCHES:
                    m_id = m["id"]
                    score = state["group_matches"][m_id]
                    match_objs.append(GroupMatch(
                        id=m_id,
                        group=m["group"],
                        round=m["round"],
                        home_id=m["home_id"],
                        away_id=m["away_id"],
                        home_score=score[0],
                        away_score=score[1]
                    ))
                g_standings = calculate_group_standings(g_letter, match_objs)
                
                # Render disclaimer if completely tied
                all_zero = all(stg.played == 0 for stg in g_standings)
                if all_zero:
                    st.caption("⚠️ Classificação parcial sujeita aos critérios de desempate.")
                
                # Render Standings Table
                render_standings_table(g_standings)

    # 2. Classificados Tab
    with step_tabs[1]:
        st.markdown("### 📊 Seleções Classificadas para o Mata-mata")
        st.caption("Avançam os dois primeiros de cada grupo e os oito melhores terceiros, conforme pontuação, saldo de gols e gols marcados.")
        
        # Check if all group matches have been simulated
        unplayed = [gm["id"] for gm in GROUP_MATCHES if state["group_matches"][gm["id"]][0] is None or state["group_matches"][gm["id"]][1] is None]
        if unplayed:
            st.warning(f"Ainda restam {len(unplayed)} jogos da fase de grupos para simular. Por favor, simule todos os jogos para liberar o mata-mata.")
        else:
            # Calculate standings
            standings = recalculate_all_standings(state)
            
            st.markdown("#### Classificados Diretos (1º e 2º)")
            direct_rows = []
            for g_letter, g_stg in standings.items():
                t1 = g_stg[0].name if len(g_stg) >= 1 else "—"
                t2 = g_stg[1].name if len(g_stg) >= 2 else "—"
                direct_rows.append({
                    "Grupo": f"Grupo {g_letter}",
                    "1º Colocado": t1,
                    "2º Colocado": t2
                })
            st.dataframe(pd.DataFrame(direct_rows), use_container_width=True, hide_index=True)
            
            st.markdown("#### Ranking dos Terceiros Colocados")
            best_thirds = get_best_third_placed_teams(standings)
            render_best_thirds_table(best_thirds)

    # 3. Mata-mata Tab
    with step_tabs[2]:
        st.markdown("### 🏆 Chave do Mata-mata")
        st.caption("Clique na seleção correspondente para avançá-la para a próxima rodada.")
        
        # Check group stage completed
        unplayed = [gm["id"] for gm in GROUP_MATCHES if state["group_matches"][gm["id"]][0] is None or state["group_matches"][gm["id"]][1] is None]
        if unplayed:
            st.error("Por favor, simule todos os jogos da Fase de Grupos primeiro!")
        else:
            # Recalculate slots
            standings = recalculate_all_standings(state)
            best_thirds_list = get_best_third_placed_teams(standings)[:8]
            best_thirds_groups = []
            for stg in best_thirds_list:
                g_letter = next(g for g, t_ids in GROUPS_TEAMS.items() if stg.team_id in t_ids)
                best_thirds_groups.append(g_letter)
                
            initial_slots = build_initial_bracket_slots(standings, best_thirds_groups)
            
            # Sync initial slots to state (only for slots 31 to 62, to prevent overwriting user knockout winners!)
            slots = state["slots"]
            for slot_id in range(31, 63):
                slots[slot_id] = initial_slots[slot_id]
            for slot_id in range(31):
                if slot_id not in slots:
                    slots[slot_id] = None
                    
            # Render bracket phases in subtabs
            phase_tabs = st.tabs(["Décima-sextas", "Oitavas", "Quartas", "Semifinais", "Final & Campeão"])
            
            # Décima-sextas (Round of 32)
            with phase_tabs[0]:
                render_bracket_round("fase_32", MAP_FASE_32, slots)
                
            # Oitavas
            with phase_tabs[1]:
                # Check if all fase_32 matches are simulated (slots 15 to 30 populated)
                missing_fase_32 = [w for _, _, w in MAP_FASE_32 if slots[w] is None]
                if missing_fase_32:
                    st.warning("Preencha todos os vencedores das Décima-sextas para liberar as Oitavas de Final.")
                else:
                    render_bracket_round("oitavas", MAP_OITAVAS, slots)
                    
            # Quartas
            with phase_tabs[2]:
                missing_oitavas = [w for _, _, w in MAP_OITAVAS if slots[w] is None]
                if missing_oitavas:
                    st.warning("Preencha todos os vencedores das Oitavas para liberar as Quartas de Final.")
                else:
                    render_bracket_round("quartas", MAP_QUARTAS, slots)
                    
            # Semifinais
            with phase_tabs[3]:
                missing_quartas = [w for _, _, w in MAP_QUARTAS if slots[w] is None]
                if missing_quartas:
                    st.warning("Preencha todos os vencedores das Quartas para liberar as Semifinais.")
                else:
                    render_bracket_round("semifinais", MAP_SEMIFINAIS, slots)
                    
            # Final & Campeão
            with phase_tabs[4]:
                missing_semis = [w for _, _, w in MAP_SEMIFINAIS if slots[w] is None]
                if missing_semis:
                    st.warning("Preencha os vencedores das Semifinais para liberar a grande Final.")
                else:
                    render_final_and_champion(slots)

    # 4. Revisão e Envio Tab
    with step_tabs[3]:
        st.markdown("### 📝 Revisão do seu Palpite" if not is_admin else "### 📝 Revisão do Resultado Oficial")
        
        # Check completeness
        unplayed = [gm["id"] for gm in GROUP_MATCHES if state["group_matches"][gm["id"]][0] is None or state["group_matches"][gm["id"]][1] is None]
        missing_winners = [i for i in range(63) if state["slots"].get(i) is None]
        
        is_complete = not (unplayed or missing_winners)
        
        if not is_complete:
            if is_admin:
                st.warning("⚠️ O resultado oficial está incompleto (competição em andamento). Como Administrador, você pode salvar o resultado oficial parcial para atualizar o ranking durante a Copa.")
            else:
                st.error("Seu palpite está incompleto. Por favor, certifique-se de que simulou todos os jogos de grupo e selecionou todos os vencedores do mata-mata (incluindo o campeão).")
                if unplayed:
                    st.write(f"- Restam {len(unplayed)} jogos da fase de grupos.")
                if missing_winners:
                    st.write(f"- Restam {len(missing_winners)} confrontos do mata-mata sem vencedor.")
        else:
            st.success("🎉 Palpite completo!" if not is_admin else "🎉 Resultado oficial completo!")
            
        # Show summary if complete or if we are admin saving partial results
        if is_complete or is_admin:
            # Show summary
            st.markdown("#### 🏆 Campeão da Copa")
            champ_id = state["slots"].get(0)
            champ_name = TEAMS[champ_id]["name"] if champ_id else "A definir"
            champ_badge = get_team_badge_path(champ_id) if champ_id else None
            
            col_c1, col_c2 = st.columns([1, 4])
            with col_c1:
                if champ_badge:
                    st.image(champ_badge, width=96)
            with col_c2:
                st.markdown(f"<h1>{champ_name}</h1>", unsafe_allow_html=True)
                
            # Show bracket overview
            with st.expander("Ver resumo do mata-mata", expanded=True):
                col_rev1, col_rev2 = st.columns(2)
                with col_rev1:
                    st.markdown("**Finalistas:**")
                    f1_id = state["slots"].get(1)
                    f2_id = state["slots"].get(2)
                    st.write(f"1. {TEAMS[f1_id]['name'] if f1_id else 'A definir'}")
                    st.write(f"2. {TEAMS[f2_id]['name'] if f2_id else 'A definir'}")
                    
                    st.markdown("**Semifinalistas:**")
                    for i in [3, 4, 5, 6]:
                        s_id = state["slots"].get(i)
                        st.write(f"- {TEAMS[s_id]['name'] if s_id else 'A definir'}")
                with col_rev2:
                    st.markdown("**Quartas de Final:**")
                    for i in range(7, 15):
                        q_id = state["slots"].get(i)
                        st.write(f"- {TEAMS[q_id]['name'] if q_id else 'A definir'}")
            
            # Submit Details
            st.markdown("---")
            st.markdown("#### Informações de Envio" if not is_admin else "#### Gravação de Resultados")
            
            # Fill prediction
            serialize_slots_to_prediction(state["slots"], prediction)
            
            # Store group matches and slots in prediction metadata
            prediction.meta["group_matches"] = state["group_matches"]
            prediction.meta["slots"] = state["slots"]
            
            # Save group visual positions (1º, 2º, 3º, 4º)
            standings = recalculate_all_standings(state)
            for g_letter, stg_list in standings.items():
                prediction.groups[g_letter] = [stg.name for stg in stg_list]
                
            # Save best thirds
            prediction.best_thirds = [TEAMS[stg.team_id]["name"] for stg in get_best_third_placed_teams(standings)[:8]]
            
            return prediction
            
    return None

def recalculate_all_standings(state) -> dict[str, list[GroupStanding]]:
    # Convert group matches state to GroupMatch objects
    match_objs = []
    for m in GROUP_MATCHES:
        m_id = m["id"]
        score = state["group_matches"][m_id]
        match_objs.append(GroupMatch(
            id=m_id,
            group=m["group"],
            round=m["round"],
            home_id=m["home_id"],
            away_id=m["away_id"],
            home_score=score[0],
            away_score=score[1]
        ))
        
    # Calculate standings for all groups
    standings = {}
    for g_letter in GROUPS_TEAMS.keys():
        standings[g_letter] = calculate_group_standings(g_letter, match_objs)
        
    return standings

def simulate_knockout_randomly(slots: dict[int, str | None]):
    # We simulate starting from Round of 32 (MAP_FASE_32) up to final
    # 1. Fase de 32 (slots 31-62 -> winner slots 15-30)
    for h, v, w in MAP_FASE_32:
        winner = random.choice([slots[h], slots[v]])
        slots[w] = winner
        
    # 2. Oitavas (slots 15-30 -> winner slots 7-14)
    for h, v, w in MAP_OITAVAS:
        winner = random.choice([slots[h], slots[v]])
        slots[w] = winner
        
    # 3. Quartas (slots 7-14 -> winner slots 3-6)
    for h, v, w in MAP_QUARTAS:
        winner = random.choice([slots[h], slots[v]])
        slots[w] = winner
        
    # 4. Semifinais (slots 3-6 -> winner slots 1-2)
    for h, v, w in MAP_SEMIFINAIS:
        winner = random.choice([slots[h], slots[v]])
        slots[w] = winner
        
    # 5. Final (slots 1-2 -> winner slot 0)
    winner = random.choice([slots[1], slots[2]])
    slots[0] = winner

def render_standings_table(standings: list[GroupStanding]):
    rows = []
    for stg in standings:
        rows.append({
            "Pos": stg.position,
            "Seleção": stg.name,
            "P": stg.points,
            "J": stg.played,
            "V": stg.wins,
            "E": stg.draws,
            "D": stg.losses,
            "GP": stg.gf,
            "GC": stg.ga,
            "SG": stg.gd,
            "%": f"{stg.percent:.1f}%"
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_best_thirds_table(best_thirds: list[GroupStanding]):
    rows = []
    for idx, stg in enumerate(best_thirds, start=1):
        g_letter = next(g for g, t_ids in GROUPS_TEAMS.items() if stg.team_id in t_ids)
        rows.append({
            "Rank": idx,
            "Seleção": stg.name,
            "Grupo": g_letter,
            "P": stg.points,
            "J": stg.played,
            "V": stg.wins,
            "E": stg.draws,
            "D": stg.losses,
            "GP": stg.gf,
            "GC": stg.ga,
            "SG": stg.gd,
            "Status": "Classificado" if idx <= 8 else "Eliminado"
        })
    df = pd.DataFrame(rows)
    
    # Styled dataframe
    def highlight_rows(val):
        color = 'background-color: rgba(46, 117, 89, 0.2)' if val == 'Classificado' else 'background-color: rgba(186, 45, 45, 0.2)'
        return color
        
    st.dataframe(df.style.map(highlight_rows, subset=['Status']), use_container_width=True, hide_index=True)

def render_bracket_round(phase_name: str, matches_mapping: list[tuple[int, int, int]], slots: dict[int, str | None]):
    col_l1, col_l2 = st.columns(2)
    
    for idx, (h, v, w) in enumerate(matches_mapping):
        col = col_l1 if idx % 2 == 0 else col_l2
        with col:
            st.markdown(f"**Confronto {idx+1}**")
            
            h_id = slots[h]
            a_id = slots[v]
            winner_id = slots[w]
            
            h_name = TEAMS[h_id]["name"] if h_id else BRACKET_SLOTS[h]["label"]
            a_name = TEAMS[a_id]["name"] if a_id else BRACKET_SLOTS[v]["label"]
            
            h_badge = get_team_badge_path(h_id) if h_id else None
            a_badge = get_team_badge_path(a_id) if a_id else None
            
            # Confrontation Box
            sub_c1, sub_vs, sub_c2 = st.columns([4, 1, 4])
            
            with sub_c1:
                if h_badge:
                    st.image(h_badge, width=32)
                btn_type = "primary" if (winner_id and winner_id == h_id) else "secondary"
                if st.button(h_name, key=f"progress_{phase_name}_{idx}_home", use_container_width=True, type=btn_type, disabled=not h_id):
                    propagate_winner(slots, h, h_id)
                    st.rerun()
                    
            with sub_vs:
                st.markdown("<div style='text-align: center; line-height: 40px;'>vs</div>", unsafe_allow_html=True)
                
            with sub_c2:
                if a_badge:
                    st.image(a_badge, width=32)
                btn_type = "primary" if (winner_id and winner_id == a_id) else "secondary"
                if st.button(a_name, key=f"progress_{phase_name}_{idx}_visitor", use_container_width=True, type=btn_type, disabled=not a_id):
                    propagate_winner(slots, v, a_id)
                    st.rerun()
            st.markdown("<br>", unsafe_allow_html=True)

def render_final_and_champion(slots: dict[int, str | None]):
    col_f1, col_vs, col_f2 = st.columns([4, 1, 4])
    
    h_id = slots[1]
    a_id = slots[2]
    winner_id = slots[0]
    
    h_name = TEAMS[h_id]["name"] if h_id else "Finalista 1"
    a_name = TEAMS[a_id]["name"] if a_id else "Finalista 2"
    
    h_badge = get_team_badge_path(h_id) if h_id else None
    a_badge = get_team_badge_path(a_id) if a_id else None
    
    with col_f1:
        st.markdown("### Finalista 1")
        if h_badge:
            st.image(h_badge, width=64)
        btn_type = "primary" if (winner_id and winner_id == h_id) else "secondary"
        if st.button(h_name, key="final_home", use_container_width=True, type=btn_type, disabled=not h_id):
            slots[0] = h_id
            st.rerun()
            
    with col_vs:
        st.markdown("<br><br><div style='text-align: center; font-size: 24px;'>vs</div>", unsafe_allow_html=True)
        
    with col_f2:
        st.markdown("### Finalista 2")
        if a_badge:
            st.image(a_badge, width=64)
        btn_type = "primary" if (winner_id and winner_id == a_id) else "secondary"
        if st.button(a_name, key="final_visitor", use_container_width=True, type=btn_type, disabled=not a_id):
            slots[0] = a_id
            st.rerun()
            
    st.markdown("---")
    st.markdown("<div style='text-align: center;'><h2>🏆 Campeã da Copa do Mundo</h2></div>", unsafe_allow_html=True)
    if winner_id:
        champ_name = TEAMS[winner_id]["name"]
        champ_badge = get_team_badge_path(winner_id)
        
        c_col1, c_col2, c_col3 = st.columns([3, 1, 3])
        with c_col2:
            if champ_badge:
                st.image(champ_badge, width=128)
            st.markdown(f"<div style='text-align: center; font-size: 20px; font-weight: bold;'>{champ_name}</div>", unsafe_allow_html=True)
    else:
        st.info("Selecione o vencedor da grande final acima para coroar a equipe campeã!")

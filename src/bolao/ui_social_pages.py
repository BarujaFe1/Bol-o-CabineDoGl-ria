from __future__ import annotations

import streamlit as st
import pandas as pd
import urllib.parse
from datetime import datetime
from .storage import load_matches, load_live_predictions, load_submissions, load_official, load_config, load_app_data_cached
from .live_scoring import calculate_live_prediction_points, calculate_live_ranking
from .scoring import rank_predictions
from .utils import normalize_participant_key
from .ui_components import render_page_header, render_kpi_grid, render_empty_state, render_badge
from .achievements import calculate_achievements
from .social import build_duel_share_text, build_taunt_text
from .ui_live_matches import is_match_open_for_prediction

def render_central_do_bolao() -> None:
    render_page_header("Central", "Central Social do Bolão", "Painel esportivo com os principais destaques, sequências e zoeiras do grupo.", "📣")
    
    ctx = load_app_data_cached()
    config = ctx.config
    submissions = ctx.submissions
    live_preds = ctx.live_predictions
    matches = ctx.matches
    official = ctx.official

    if not submissions and not live_preds:
        st.info("Nenhum palpite enviado ainda no sistema.")
        return

    # Líderes
    classic_leader = "—"
    live_leader = "—"
    combined_leader = "—"
    lanterna = "—"
    
    # Calcular rankings
    if submissions and official:
        from .scoring import ScoreConfig
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )
        classic_ranks = rank_predictions(submissions, official, score_config)
        if classic_ranks:
            classic_leader = classic_ranks[0].participant
            
    live_ranks = calculate_live_ranking(live_preds, matches, config)
    if live_ranks:
        live_leader = live_ranks[0]["participant"]
        lanterna = live_ranks[-1]["participant"]

    combined_enabled = config.get("combined_ranking_enabled", False)
    if combined_enabled and official:
        combined_rules = config.get("combined_ranking", {})
        classic_weight = combined_rules.get("classic_weight", 1.0)
        live_weight = combined_rules.get("live_weight", 1.0)
        
        classic_dict = {normalize_participant_key(s.participant): s for s in classic_ranks}
        live_dict = {s["participant_key"]: s for s in live_ranks}
        all_keys = set(classic_dict.keys()).union(live_dict.keys())
        
        combined_list = []
        for pk in all_keys:
            c_s = classic_dict.get(pk)
            l_s = live_dict.get(pk)
            c_p = c_s.total if c_s else 0
            l_p = l_s["total"] if l_s else 0
            combined_list.append({"name": c_s.participant if c_s else l_s["participant"], "total": c_p * classic_weight + l_p * live_weight})
        combined_list.sort(key=lambda x: -x["total"])
        if combined_list:
            combined_leader = combined_list[0]["name"]

    # Render KPIs
    kpi_items = [
        {"label": "Líder Clássico", "value": classic_leader},
        {"label": "Líder Jogo a Jogo", "value": live_leader},
    ]
    if combined_enabled:
        kpi_items.append({"label": "Líder Geral", "value": combined_leader})
    render_kpi_grid(kpi_items)

    # Zoeira do dia (Taunt)
    st.markdown("#### 🗣️ Provocação da Rodada")
    taunt_ctx = {"nome": live_leader, "kind": "lider"}
    if live_leader != "—":
        st.markdown(f'<div class="callout warning">📢 {build_taunt_text(taunt_ctx)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="callout info">📢 A Copa está começando! Quem assumirá a liderança primeiro?</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### ⏰ Próximos Fechamentos")
        now = datetime.now().isoformat()
        upcoming = [m for m in matches if m.starts_at and m.starts_at > now and m.status != "result_approved"]
        upcoming.sort(key=lambda x: x.starts_at)
        
        if not upcoming:
            st.write("Nenhum jogo futuro agendado.")
        else:
            for m in upcoming[:3]:
                st.write(f"⚽ **{m.home_team} x {m.away_team}**")
                st.caption(f"Fecha em: {m.lock_at.replace('T', ' ')}")

    with col2:
        st.markdown("#### 📢 Últimos Acontecimentos")
        # Load only public events
        from .storage import load_events
        events = load_events(limit=5, visibility="public")
        if not events:
            st.write("Sem atividades recentes.")
        else:
            for e in events:
                ts = e.get("timestamp", "").split("T")[1][:5] if "T" in e.get("timestamp", "") else "—"
                st.write(f"⏱️ **{ts}** — {e.get('message')}")


def render_palpites_do_grupo() -> None:
    render_page_header("Palpites do Grupo", "Palpites Coletivos", "Veja o que cada participante palpitou para os jogos.", "👥")
    
    ctx = load_app_data_cached()
    matches = ctx.matches
    live_preds = ctx.live_predictions
    submissions = ctx.submissions
    config = ctx.config

    if not matches:
        st.info("Nenhum jogo agendado.")
        return

    matches.sort(key=lambda m: (m.starts_at or "", m.sort_order))

    # Escolher o jogo
    selected_match = st.selectbox(
        "Selecione uma partida para ver os palpites", 
        matches, 
        format_func=lambda m: f"{m.home_team} x {m.away_team} ({m.round_label})"
    )

    if not selected_match:
        return

    m = selected_match
    now = datetime.now().isoformat()
    is_open = is_match_open_for_prediction(m, now)

    st.markdown(f"#### Palpites para: {m.home_team} x {m.away_team}")
    
    # Mostrar um aviso caso esteja aberto, mas continuar exibindo os palpites
    if is_open:
        st.info("🟢 O jogo está aberto para palpites! Palpites do grupo são atualizados em tempo real.")

    # Revelar palpites
    match_preds = [lp for lp in live_preds if lp.match_id == m.match_id]
    if not match_preds:
        st.info("Ninguém palpitou nesta partida.")
        return

    data = []
    for lp in match_preds:
        points_gained = "—"
        if m.status == "result_approved":
            res = calculate_live_prediction_points(lp, m, config)
            points_gained = f"{res['points']} pts"
            
        data.append({
            "Participante": lp.participant_name,
            "Palpite": f"{lp.predicted_home_goals} x {lp.predicted_away_goals}",
            "Pontos Ganhos": points_gained,
            "Envio": lp.submitted_at.replace("T", " ") if lp.submitted_at else "—"
        })
        
    st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)


def render_analise_dos_palpites() -> None:
    render_page_header("Análise", "Análise dos Palpites vs Realidade", "Estatísticas retrospectivas de acertos, erros e zebras.", "📊")
    
    ctx = load_app_data_cached()
    matches = ctx.matches
    live_preds = ctx.live_predictions
    submissions = ctx.submissions
    config = ctx.config

    approved_matches = [m for m in matches if m.status == "result_approved" and m.official_home_goals is not None and m.official_away_goals is not None]
    if not approved_matches:
        st.info("Nenhuma partida concluída e aprovada ainda para realizar a análise retrospectiva.")
        return

    st.markdown("#### 🎯 Maiores Pontuadores da Rodada")
    # Agrupar por rodada
    rounds = sorted(list(set(m.round_label for m in approved_matches)))
    selected_round = st.selectbox("Escolha a rodada para analisar", rounds)
    
    round_matches = [m for m in approved_matches if m.round_label == selected_round]
    round_match_ids = {m.match_id for m in round_matches}
    
    round_preds = [lp for lp in live_preds if lp.match_id in round_match_ids]
    round_ranks = calculate_live_ranking(round_preds, round_matches, config)
    
    if round_ranks:
        sub_df = pd.DataFrame([{
            "Posição": r["position"],
            "Participante": r["participant"],
            "Pontos na Rodada": r["total"],
            "Placares Exatos": r["exact_scores"],
            "Aproveitamento": f"{int(r['hit_rate']*100)}%"
        } for r in round_ranks])
        st.dataframe(sub_df, width="stretch", hide_index=True)
    else:
        st.caption("Sem palpites computados para esta rodada.")

    # Estatísticas de Zebras
    st.markdown("#### 🦓 Acertos de Zebras (Divergência do Grupo)")
    zebra_hits_list = []
    
    for m in approved_matches:
        match_preds = [lp for lp in live_preds if lp.match_id == m.match_id]
        total_p = len(match_preds)
        if total_p == 0:
            continue
            
        home_votes = sum(1 for lp in match_preds if lp.predicted_home_goals > lp.predicted_away_goals)
        away_votes = sum(1 for lp in match_preds if lp.predicted_home_goals < lp.predicted_away_goals)
        draw_votes = sum(1 for lp in match_preds if lp.predicted_home_goals == lp.predicted_away_goals)
        
        real_outcome = "draw"
        if m.official_home_goals > m.official_away_goals:
            real_outcome = "home"
        elif m.official_home_goals < m.official_away_goals:
            real_outcome = "away"
            
        votes_for_real = home_votes if real_outcome == "home" else (away_votes if real_outcome == "away" else draw_votes)
        pct_votes_for_real = (votes_for_real / total_p)
        
        # Se menos de 30% apostaram no resultado real, é zebra!
        if pct_votes_for_real < 0.30:
            # Encontrar quem acertou
            winners = []
            for lp in match_preds:
                res = calculate_live_prediction_points(lp, m, config)
                if res["flags"].get("outcome"):
                    winners.append(lp.participant_name)
            
            zebra_hits_list.append({
                "Jogo": f"{m.home_team} x {m.away_team}",
                "Placar Oficial": f"{m.official_home_goals} x {m.official_away_goals}",
                "Apoio do Grupo": f"{int(pct_votes_for_real * 100)}%",
                "Quem Acertou": ", ".join(winners) if winners else "Ninguém"
            })
            
    if zebra_hits_list:
        st.dataframe(pd.DataFrame(zebra_hits_list), width="stretch", hide_index=True)
    else:
        st.write("Nenhum resultado classificado como zebra ocorreu na Copa ainda.")


def render_duelo_de_palpites() -> None:
    render_page_header("Duelo", "Duelo Direto de Palpites", "Compare o desempenho de dois participantes lado a lado.", "⚔️")
    
    ctx = load_app_data_cached()
    submissions = ctx.submissions
    live_preds = ctx.live_predictions
    matches = ctx.matches
    official = ctx.official
    config = ctx.config

    names = sorted(list(set([p.participant for p in submissions] + [p.participant_name for p in live_preds])), key=lambda x: x.lower())
    if len(names) < 2:
        st.info("São necessários pelo menos 2 participantes para iniciar um duelo.")
        return

    col1, col2 = st.columns(2)
    with col1:
        player_a = st.selectbox("Escolha o Participante A", names, index=0, key="duel_player_a")
    with col2:
        player_b = st.selectbox("Escolha o Participante B", names, index=min(1, len(names)-1), key="duel_player_b")

    if player_a == player_b:
        st.warning("Selecione participantes diferentes para duelar.")
        return

    pkey_a = normalize_participant_key(player_a)
    pkey_b = normalize_participant_key(player_b)

    # Rankings
    classic_points_a = classic_points_b = 0
    live_points_a = live_points_b = 0
    
    if submissions and official:
        from .scoring import ScoreConfig
        from .constants import DEFAULT_WEIGHTED_RULES, DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES
        score_config = ScoreConfig(
            mode=config.get("scoring_mode", "v2"),
            weighted_rules=config.get("weighted_rules", dict(DEFAULT_WEIGHTED_RULES)),
            uniform_rules=config.get("uniform_rules", dict(DEFAULT_UNIFORM_RULES)),
            v2_rules=config.get("v2_rules", dict(DEFAULT_V2_RULES)),
        )
        classic_scores = rank_predictions(submissions, official, score_config)
        sc_a = next((s for s in classic_scores if normalize_participant_key(s.participant) == pkey_a), None)
        sc_b = next((s for s in classic_scores if normalize_participant_key(s.participant) == pkey_b), None)
        classic_points_a = sc_a.total if sc_a else 0
        classic_points_b = sc_b.total if sc_b else 0

    live_scores = calculate_live_ranking(live_preds, matches, config)
    ls_a = next((s for s in live_scores if s["participant_key"] == pkey_a), None)
    ls_b = next((s for s in live_scores if s["participant_key"] == pkey_b), None)
    live_points_a = ls_a["total"] if ls_a else 0
    live_points_b = ls_b["total"] if ls_b else 0

    st.markdown(f"#### 📊 Confronto: {player_a} vs {player_b}")
    
    # KPI Grid
    kpis = [
        {"label": f"Pontos {player_a} (Jogo a Jogo)", "value": str(live_points_a)},
        {"label": f"Pontos {player_b} (Jogo a Jogo)", "value": str(live_points_b)},
    ]
    render_kpi_grid(kpis)

    # Discordâncias no Jogo a Jogo (apenas bloqueados)
    now = datetime.now().isoformat()
    locked_match_ids = set(m.match_id for m in matches if m.status == "result_approved" or not is_match_open_for_prediction(m, now))

    discord_list = []
    diff_count = 0
    
    for m in matches:
        if m.match_id in locked_match_ids:
            p_a = next((lp for lp in live_preds if lp.match_id == m.match_id and (lp.participant_key or normalize_participant_key(lp.participant_name)) == pkey_a), None)
            p_b = next((lp for lp in live_preds if lp.match_id == m.match_id and (lp.participant_key or normalize_participant_key(lp.participant_name)) == pkey_b), None)
            
            if p_a or p_b:
                guess_a = f"{p_a.predicted_home_goals} x {p_a.predicted_away_goals}" if p_a else "Não palpitou"
                guess_b = f"{p_b.predicted_home_goals} x {p_b.predicted_away_goals}" if p_b else "Não palpitou"
                
                if guess_a != guess_b:
                    diff_count += 1
                    discord_list.append({
                        "Jogo": f"{m.home_team} x {m.away_team}",
                        player_a: guess_a,
                        player_b: guess_b,
                        "Resultado Oficial": f"{m.official_home_goals} x {m.official_away_goals}" if m.status == "result_approved" else "Pendente"
                    })
                    
    # Determinar líder do duelo
    leader = "Empate"
    if live_points_a > live_points_b:
        leader = player_a
    elif live_points_b > live_points_a:
        leader = player_b

    st.markdown("#### 📱 Compartilhar Duelo no WhatsApp")
    share_duel_txt = build_duel_share_text(player_a, player_b, live_points_a, live_points_b, leader, diff_count)
    st.code(share_duel_txt, language="text")
    
    encoded = urllib.parse.quote(share_duel_txt)
    st.link_button("💬 Enviar Duelo no WhatsApp", f"https://api.whatsapp.com/send?text={encoded}", type="primary", width="stretch")

    st.markdown("#### ⚔️ Divergências de Placares em Jogos Bloqueados")
    if discord_list:
        st.dataframe(pd.DataFrame(discord_list), width="stretch", hide_index=True)
    else:
        st.caption("Os dois participantes concordaram em todos os palpites dos jogos bloqueados até o momento.")


def render_transparencia() -> None:
    render_page_header("Transparência", "Auditoria e Transparência do Bolão", "Validação pública dos parâmetros, bloqueios e regras operacionais.", "🛡️")
    
    ctx = load_app_data_cached()
    config = ctx.config
    matches = ctx.matches
    submissions = ctx.submissions

    st.markdown("#### ⚙️ Parâmetros Ativos de Pontuação")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Modo Clássico:**")
        st.write(f"- Método de cálculo: `{config.get('scoring_mode', 'v2').upper()}`")
        st.write(f"- Submissões clássicas travadas: `{'Sim' if config.get('classic_submissions_locked', False) or config.get('is_bolao_locked', False) else 'Não'}`")
    with col2:
        st.markdown("**Modo Jogo a Jogo:**")
        st.write(f"- Prazo de bloqueio individual: `{config.get('live_lock_minutes_before_match', 10)} minutos antes do jogo`")
        st.write(f"- Regra de acerto exato: `{config.get('live_scoring', {}).get('exact_score_mode', 'isolated_max')}`")

    # KPIs de Integridade
    kpi_items = [
        {"label": "Cadastros Clássicos", "value": str(len(submissions))},
        {"label": "Palpites Jogo a Jogo", "value": str(len(ctx.live_predictions))},
        {"label": "Eventos de Auditoria", "value": str(len(ctx.events))},
    ]
    render_kpi_grid(kpi_items)

    st.markdown("#### 🏁 Regras de Desempate (Ranking Oficial)")
    st.markdown(
        """
        Em caso de igualdade de pontos nos rankings, os critérios aplicados serão:
        1. **Modo Clássico:**
           * Maior pontuação obtida na fase de mata-mata.
           * Maior quantidade de acertos de placares exatos na fase de grupos.
           * Ordem cronológica de envio (palpite enviado primeiro vence).
        2. **Modo Jogo a Jogo:**
           * Maior quantidade de acertos de placares exatos.
           * Maior percentual de aproveitamento de palpites (hit rate).
           * Menor quantidade de palpites perdidos (esqueceu de palpitar).
        """
    )


def render_regras_do_bolao() -> None:
    render_page_header("Regras", "Regras e Como Funciona o Bolão", "Instruções completas para participar e pontuar nos dois modos.", "📖")
    
    st.markdown(
        """
        ### 🏆 Dois Modos de Disputa Independentes e Paralelos
        
        O **Bolão da Cabine do Glória** oferece dois modos de participação. Você pode competir em apenas um deles, ou em ambos simultaneamente!
        
        ---
        
        ### 1. 📋 MODO CLÁSSICO
        Neste modo, você preenche a simulação completa da Copa do Mundo 2026 de uma só vez (grupos, classificados, mata-mata e o campeão):
        * **Preenchimento:** Realizado na aba **Palpite Clássico** antes do prazo final do bolão.
        * **Edição:** Permitida a qualquer momento enquanto as submissões clássicas estiverem abertas.
        * **Visualização dos outros:** Os palpites de todos os participantes do clássico serão revelados publicamente após o encerramento do prazo.
        * **Ranking:** Gera o **Ranking Clássico** baseado nas regras de acertos de posições, classificados e campeão.
        
        ---
        
        ### 2. ⚽ MODO JOGO A JOGO
        Palpite individualmente em cada partida da Copa:
        * **Preenchimento:** Na aba **Jogos de Hoje**, informe seus placares jogo por jogo.
        * **Prazos:** Você pode enviar ou alterar seu palpite até **10 minutos antes** do início de cada partida.
        * **Privacidade:** Os palpites de um jogo ficam ocultos e só são revelados ao grupo após o bloqueio das apostas daquele jogo (10 minutos antes do jogo começar).
        * **Ranking:** Gera o **Ranking Jogo a Jogo** focado na precisão de placares individuais.
        
        ---
        
        ### 📊 Critérios de Pontuação do Modo Jogo a Jogo
        
        Os pontos por partida no Modo Jogo a Jogo são calculados da seguinte forma:
        * **Placar Exato:** **5 pontos** (se acertar em cheio o placar exato).
        * **Resultado Correto (Vitória/Empate):** **3 pontos** (se acertar o vencedor ou empate, mas errar o placar).
        * **Gols de um Time:** **1 ponto** por time (se acertar a quantidade de gols marcada por um dos times).
        * **Saldo de Gols:** **1 ponto** (se acertar a diferença de gols entre os times).
        
        *Nota: No modo padrão (isolated_max), se você acertar o placar exato, recebe a pontuação máxima de 5 pontos (não acumula os bônus secundários). Caso contrário, soma-se os bônus aplicáveis de resultado, gols e saldo.*
        
        ---
        
        ### 🥈 RANKING GERAL (Combinado)
        Se ativado pelo administrador, o **Ranking Geral** exibe a consolidação das pontuações dos dois rankings (Clássico + Jogo a Jogo) com base nos pesos configurados:
        * Pontuação Geral = `(Pontos Clássico * Peso Clássico) + (Pontos Jogo a Jogo * Peso Jogo a Jogo)`.
        * Participantes que jogam apenas um modo aparecem com 0 pontos no outro modo.
        """
    )

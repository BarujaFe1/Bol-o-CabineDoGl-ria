from __future__ import annotations

import random
from typing import Any

def build_classic_share_text(participant: str, champion: str, finalist_1: str, finalist_2: str, code: str) -> str:
    """
    Texto pós-palpite clássico.
    """
    return (
        f"🏆 Meu palpite no Bolão da Cabine do Glória (Modo Clássico) está feito!\n\n"
        f"Campeão: {champion}\n"
        f"Final: {finalist_1} x {finalist_2}\n"
        f"Código de Confirmação: {code}\n\n"
        f"Acompanhe o ranking e participe também no Jogo a Jogo!"
    )

def build_live_match_share_text(participant: str, match: Any, pred_home: int, pred_away: int, code: str | None = None) -> str:
    """
    Texto para compartilhamento de palpite individual de jogo.
    """
    home = match.home_team if hasattr(match, 'home_team') else match.get("home_team", "Mandante")
    away = match.away_team if hasattr(match, 'away_team') else match.get("away_team", "Visitante")
    phase = match.round_label if hasattr(match, 'round_label') else match.get("round_label", "Copa")
    
    code_str = f"\nCódigo: {code}" if code else ""
    return (
        f"⚽ Palpite feito por {participant} ({phase})!\n"
        f"👉 {home} {pred_home} x {pred_away} {away}\n"
        f"Bolão da Cabine do Glória!{code_str}"
    )

def build_daily_games_text(matches: list[Any]) -> str:
    """
    Chamada dos jogos do dia/agenda para palpitar.
    """
    lines = []
    lines.append("🔥 Jogos de hoje no Bolão da Cabine do Glória!")
    lines.append("")
    lines.append("Não esqueça de palpitar:")
    
    for m in matches:
        lock_str = "—"
        if hasattr(m, 'lock_at') and m.lock_at:
            lock_str = m.lock_at.split("T")[1][:5]
        elif isinstance(m, dict) and m.get("lock_at"):
            lock_str = m.get("lock_at").split("T")[1][:5]
            
        home = m.home_team if hasattr(m, 'home_team') else m.get("home_team", "Mandante")
        away = m.away_team if hasattr(m, 'away_team') else m.get("away_team", "Visitante")
        
        lines.append(f"⚽ {home} x {away} — fecha às {lock_str}")
        
    lines.append("")
    lines.append("Entre no app e garanta seus pontos!")
    return "\n".join(lines)

def build_live_daily_share_text(matches: list[Any]) -> str:
    """
    Mantido para retrocompatibilidade.
    """
    return build_daily_games_text(matches)

def build_ranking_share_text(classic_ranking: list[Any], live_ranking: list[Any], combined_ranking: list[Any] = None) -> str:
    """
    Resumo dos rankings atuais.
    """
    lines = []
    lines.append("🏆 *Classificação Atualizada — Bolão da Cabine do Glória*")
    lines.append("")
    
    if combined_ranking:
        lines.append("*RANKING GERAL (Combinado):*")
        for idx, r in enumerate(combined_ranking[:3], start=1):
            name = r.get("participant", "—")
            pts = r.get("total", 0)
            lines.append(f"{idx}º {name} — {pts} pts")
        lines.append("")
        
    if classic_ranking:
        lines.append("*Ranking Clássico:*")
        lead = classic_ranking[0]
        name = lead.participant if hasattr(lead, 'participant') else lead.get("participant", "—")
        pts = lead.total if hasattr(lead, 'total') else lead.get("total", 0)
        lines.append(f"🥇 {name} — {pts} pts")
        lines.append("")
        
    if live_ranking:
        lines.append("*Ranking Jogo a Jogo:*")
        lead = live_ranking[0]
        name = lead.get("participant") if isinstance(lead, dict) else (lead.participant if hasattr(lead, 'participant') else "—")
        pts = lead.get("total") if isinstance(lead, dict) else (lead.total if hasattr(lead, 'total') else 0)
        lines.append(f"🥇 {name} — {pts} pts")
        
    lines.append("")
    lines.append("Confira a tabela completa no app!")
    return "\n".join(lines)

def build_round_summary_text(round_label: str, matches: list[Any], leaders: list[str]) -> str:
    """
    Gera resumo social da rodada.
    """
    leaders_str = ", ".join(leaders) if leaders else "Disputa acirrada"
    lines = [
        f"📝 *Resumo da {round_label} — Bolão Copa 2026* \n",
        f"Líderes da rodada: {leaders_str}",
        "Jogos da rodada:"
    ]
    for m in matches[:5]:
        home = m.home_team if hasattr(m, 'home_team') else m.get("home_team", "")
        away = m.away_team if hasattr(m, 'away_team') else m.get("away_team", "")
        o_h = m.official_home_goals if hasattr(m, 'official_home_goals') else m.get("official_home_goals")
        o_a = m.official_away_goals if hasattr(m, 'official_away_goals') else m.get("official_away_goals")
        if o_h is not None and o_a is not None:
            lines.append(f"✅ {home} {o_h} x {o_a} {away}")
            
    lines.append("\nAcesse o painel esportivo do bolão para ver todas as estatísticas!")
    return "\n".join(lines)

def build_duel_share_text(player_a: str, player_b: str, score_a: float, score_b: float, leader: str, diff_count: int) -> str:
    """
    Gera texto de compartilhamento para duelos.
    """
    winner_text = f"🔥 {leader} está na frente!" if leader != "Empate" else "⚖️ Duelo totalmente empatado!"
    return (
        f"⚔️ *DUELO DE PALPITES — Bolão Cabine do Glória*\n\n"
        f"👤 *{player_a}*: {score_a} pts\n"
        f"👤 *{player_b}*: {score_b} pts\n\n"
        f"Discordâncias em jogos bloqueados: {diff_count}\n"
        f"{winner_text}\n\n"
        f"Veja o confronto direto no Duelo de Palpites do app!"
    )

def build_my_card_share_text(player_name: str, pos_classic: int | str, pos_live: int | str, pos_geral: int | str, pts_classic: int, pts_live: int) -> str:
    """
    Texto para compartilhamento da cartela pessoal.
    """
    return (
        f"🏆 *Minha Cartela no Bolão da Copa 2026* 🏆\n"
        f"Participante: {player_name}\n\n"
        f"📊 *Pontuação e Posições:*\n"
        f"• Clássico: {pts_classic} pts (Posição: {pos_classic}º)\n"
        f"• Jogo a Jogo: {pts_live} pts (Posição: {pos_live}º)\n"
        f"• Geral Combinado: Posição: {pos_geral}º\n\n"
        f"Quem aí vai tentar bater meus palpites? Envie o seu também!"
    )

def build_taunt_text(context: dict[str, Any]) -> str:
    """
    Gera provocações leves automáticas baseadas no contexto.
    """
    nome = context.get("nome", "Alguém")
    campeao = context.get("campeao", "sua seleção")
    kind = context.get("kind", "lider")
    
    phrases = []
    if kind == "lider":
        phrases = [
            f"🥇 {nome} está liderando e já pode começar a ser cobrado no grupo.",
            f"🔥 {nome} está no topo! Sorte ou puro conhecimento técnico?",
            f"👀 {nome} assumiu a liderança. Alguém vai buscar?"
        ]
    elif kind == "lanterna":
        phrases = [
            f"😭 {nome} está segurando a tabela com muita coragem.",
            f"🐴 {nome} está esperando as zebras para decolar no ranking.",
            f"⚠️ {nome} está economizando pontos para a fase final."
        ]
    elif kind == "campeao":
        phrases = [
            f"🏆 {nome} apostou em {campeao}. Coragem ou visão?",
            f"🧐 Será que {nome} vai acertar {campeao} como campeão?"
        ]
    elif kind == "exato":
        phrases = [
            f"🎯 {nome} cravou o placar exato do jogo! Pode pedir música no Fantástico.",
            f"🔥 Que visão! {nome} acertou em cheio o placar exato."
        ]
    elif kind == "esqueceu":
        phrases = [
            f"😭 {nome} esqueceu de palpitar a tempo. O grupo não perdoa a vacilada!",
            f"⏰ O tempo passou e {nome} ficou sem palpitar nesta rodada."
        ]
    else:
        phrases = [
            f"⚽ O bolão está pegando fogo e o grupo não perdoa erro!"
        ]
        
    return random.choice(phrases)

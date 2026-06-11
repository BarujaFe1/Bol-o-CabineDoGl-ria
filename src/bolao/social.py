from __future__ import annotations

import random
from typing import Any

def build_classic_share_text(participant: str, champion: str, finalist_1: str, finalist_2: str, code: str) -> str:
    """
    Texto pós-palpite clássico.
    """
    return (
        f"🏆 Meu palpite no Bolão da Cabine do Glória está feito!\n\n"
        f"Campeão: {champion}\n"
        f"Final: {finalist_1} x {finalist_2}\n"
        f"Código: {code}\n\n"
        f"Agora é acompanhar o ranking e aguentar a zoeira do grupo."
    )

def build_live_daily_share_text(matches: list[Any]) -> str:
    """
    Chamada dos jogos do dia para o WhatsApp.
    """
    lines = []
    lines.append("🔥 Jogos de hoje no bolão!")
    lines.append("")
    lines.append("Ainda dá para palpitar:")
    
    for m in matches:
        # Expected format: "starts_at" or "lock_at"
        lock_str = "—"
        if hasattr(m, 'lock_at') and m.lock_at:
            lock_str = m.lock_at.split("T")[1][:5]
        elif isinstance(m, dict) and m.get("lock_at"):
            lock_str = m.get("lock_at").split("T")[1][:5]
            
        home = m.home_team if hasattr(m, 'home_team') else m.get("home_team", "Mandante")
        away = m.away_team if hasattr(m, 'away_team') else m.get("away_team", "Visitante")
        
        lines.append(f"⚽ {home} x {away} — fecha às {lock_str}")
        
    lines.append("")
    lines.append("Entra no app e não vacila!")
    return "\n".join(lines)

def build_ranking_share_text(classic_ranking: list[Any], live_ranking: list[Any]) -> str:
    """
    Resumo do ranking atual.
    """
    lines = []
    lines.append("🔥 Atualização do Bolão da Cabine do Glória")
    lines.append("")
    
    if classic_ranking:
        # s is a ScoreBreakdown object
        lead = classic_ranking[0]
        # Check if s has participant or s is a dict
        name = lead.participant if hasattr(lead, 'participant') else lead.get("participant", "—")
        pts = lead.total if hasattr(lead, 'total') else lead.get("total", 0)
        lines.append(f"Clássico:\n🥇 {name} — {pts} pts")
        lines.append("")
        
    if live_ranking:
        lead = live_ranking[0]
        name = lead.get("participant") if isinstance(lead, dict) else (lead.participant if hasattr(lead, 'participant') else "—")
        pts = lead.get("total") if isinstance(lead, dict) else (lead.total if hasattr(lead, 'total') else 0)
        lines.append(f"Jogo a Jogo:\n🥇 {name} — {pts} pts")
        
    return "\n".join(lines)

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

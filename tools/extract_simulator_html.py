import re
import os
import json

html_path = r"C:\dev\BolaoCopa\Simulador da Copa do Mundo 2026.html"
output_path = r"C:\dev\BolaoCopa\src\bolao\worldcup_2026_data.py"

def main():
    print(f"Reading HTML from: {html_path}")
    if not os.path.exists(html_path):
        print(f"Error: {html_path} does not exist.")
        return

    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Extract Teams
    # Find all segments split by class="rowteam" to parse them robustly
    segments = content.split('class="rowteam"')
    teams = {}
    for seg in segments[1:]:
        end_idx = seg.find('</div>\n<div class="rowteam"')
        if end_idx == -1:
            end_idx = seg.find('</div>\n</div')
        if end_idx == -1:
            end_idx = 1000  # fallback
        block = seg[:end_idx]

        # Extract data-team-id
        id_m = re.search(r'data-team-id="(\d+)"', block)
        if not id_m:
            continue
        t_id = id_m.group(1)

        # Extract name
        name_m = re.search(r'class="rowteam__name"[^>]*>(?P<name>[^<]+)<', block)
        t_name = name_m.group("name").strip() if name_m else None

        # Extract abbr
        abbr_m = re.search(r'class="rowteam__abbr"[^>]*>(?P<abbr>[^<]+)<', block)
        t_abbr = abbr_m.group("abbr").strip() if abbr_m else None

        # Extract badge src
        badge_m = re.search(r'<img[^>]*class="rowteam__badge"[^>]*src="(?P<src>[^"]+)"', block)
        if not badge_m:
            badge_m = re.search(r'<img[^>]*src="(?P<src>[^"]+)"', block)
        t_badge = badge_m.group("src").strip() if badge_m else None

        if t_id and t_name and t_abbr:
            # Normalize path or keep as is
            teams[t_id] = {
                "id": t_id,
                "name": t_name,
                "abbr": t_abbr,
                "badge": t_badge
            }

    print(f"Extracted {len(teams)} teams.")

    # 2. Extract Groups
    # Find <div class="group ... " data-group-name="Grupo X" data-teams-id="1,2,3,4">
    group_pattern = re.compile(
        r'class="group[^"]*"[^>]*data-group-name="(?P<group_name>Grupo\s+[A-L])"[^>]*data-teams-id="(?P<team_ids>[^"]+)"',
        re.IGNORECASE
    )
    groups = {}
    for m in group_pattern.finditer(content):
        g_name = m.group("group_name").strip()
        g_letter = g_name.split()[-1]
        g_teams = [tid.strip() for tid in m.group("team_ids").split(",")]
        groups[g_letter] = g_teams

    print(f"Extracted {len(groups)} groups.")

    # Map team_id to its group letter
    team_to_group = {}
    for g_letter, t_ids in groups.items():
        for tid in t_ids:
            team_to_group[tid] = g_letter

    # 3. Extract Matches
    # Matches look like:
    # <div class="match" data-match-timestamp="..." data-round="..." data-match-id="..." data-phase="..." data-brackets="...">
    # Let's find all occurrences of class="match"
    matches = []
    
    # We locate each match div, and look ahead to extract its inner content
    match_div_indices = [m.start() for m in re.finditer(r'<div[^>]*class="match"[^>]*>', content, re.IGNORECASE)]
    
    for idx, start_pos in enumerate(match_div_indices):
        # We take a snippet of the HTML around this match
        end_pos = match_div_indices[idx+1] if idx + 1 < len(match_div_indices) else len(content)
        # 1500 chars is usually enough for one match block
        sub_content = content[start_pos:min(start_pos + 2000, end_pos)]
        
        # Parse attributes from the main div tag
        div_tag_m = re.match(r'^<div[^>]*class="match"[^>]*>', sub_content, re.IGNORECASE)
        if not div_tag_m:
            continue
        div_tag = div_tag_m.group(0)
        
        m_id_m = re.search(r'data-match-id="(?P<val>\d+)"', div_tag, re.IGNORECASE)
        if not m_id_m:
            continue
        m_id = m_id_m.group("val")
        
        m_phase_m = re.search(r'data-phase="(?P<val>\d+)"', div_tag, re.IGNORECASE)
        phase = m_phase_m.group("val") if m_phase_m else ""
        
        # Only process Group phase matches (phase 183)
        if phase != "183":
            continue
            
        m_round_m = re.search(r'data-round="(?P<val>\d*)"', div_tag, re.IGNORECASE)
        round_num = m_round_m.group("val") if m_round_m else ""
        
        m_brackets_m = re.search(r'data-brackets="(?P<val>[^"]*)"', div_tag, re.IGNORECASE)
        brackets = m_brackets_m.group("val") if m_brackets_m else ""
        
        # Extract team IDs inside
        home_m = re.search(r'data-situation="home"[^>]*data-team-id="(?P<id>\d+)"', sub_content, re.IGNORECASE)
        away_m = re.search(r'data-situation="visitor"[^>]*data-team-id="(?P<id>\d+)"', sub_content, re.IGNORECASE)
        
        home_id = home_m.group("id") if home_m else None
        away_id = away_m.group("id") if away_m else None
        
        # Extract venue, date, time
        stadium_m = re.search(r'class="match__stadium"[^>]*title="(?P<title>[^"]+)"', sub_content, re.IGNORECASE)
        stadium = stadium_m.group("title").strip() if stadium_m else ""
        
        date_m = re.search(r'class="match__date[^"]*"[^>]*>(?P<val>[^<]+)<', sub_content, re.IGNORECASE)
        date = date_m.group("val").strip() if date_m else ""
        
        hour_m = re.search(r'class="match__hour"[^>]*>(?P<val>[^<]+)<', sub_content, re.IGNORECASE)
        hour = hour_m.group("val").strip() if hour_m else ""
        
        group_letter = team_to_group.get(home_id) or team_to_group.get(away_id) or ""
        
        matches.append({
            "id": m_id,
            "phase": phase,
            "round": round_num,
            "group": group_letter,
            "home_id": home_id,
            "away_id": away_id,
            "stadium": stadium,
            "date": date,
            "hour": hour
        })

    print(f"Extracted {len(matches)} group matches.")

    # 4. Extract Bracket Slots
    # e.g., id="id31" data-key="dezesseis1_time1" ... <p class="team-label">1ºE</p>
    bracket_slots = {}
    bracket_matches = re.finditer(r'id="id(?P<num>\d+)"[^>]*data-key="(?P<key>[^"]+)"[^>]*>', content, re.IGNORECASE)
    for m in bracket_matches:
        num = int(m.group("num"))
        key = m.group("key").strip()
        
        sub = content[m.start():m.start()+350]
        label_m = re.search(r'class="team-label"[^>]*>(?P<label>[^<]*)<', sub, re.IGNORECASE)
        label = label_m.group("label").strip() if label_m else ""
        
        bracket_slots[num] = {
            "id": num,
            "key": key,
            "label": label
        }

    print(f"Extracted {len(bracket_slots)} bracket slots.")

    # Sort bracket slots by ID
    sorted_slots = [bracket_slots[i] for i in sorted(bracket_slots.keys())]

    # Write output to worldcup_2026_data.py
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("# -*- coding: utf-8 -*-\n")
        out.write("\"\"\"\n")
        out.write("Dados estáticos extraídos do Simulador da Copa do Mundo 2026.html\n")
        out.write("Gerado de forma automatizada pelo script extract_simulator_html.py\n")
        out.write("\"\"\"\n\n")
        
        # Write TEAMS
        out.write("TEAMS = {\n")
        for tid, tinfo in sorted(teams.items(), key=lambda x: int(x[0])):
            out.write(f"    {repr(tid)}: {repr(tinfo)},\n")
        out.write("}\n\n")
        
        # Write GROUPS_TEAMS
        out.write("GROUPS_TEAMS = {\n")
        for g_letter in sorted(groups.keys()):
            out.write(f"    {repr(g_letter)}: {repr(groups[g_letter])},\n")
        out.write("}\n\n")
        
        # Write GROUP_MATCHES
        out.write("GROUP_MATCHES = [\n")
        # Sort matches by group, then round, then date/hour
        for m in sorted(matches, key=lambda x: (x["group"], x["round"], x["date"], x["hour"])):
            out.write(f"    {repr(m)},\n")
        out.write("]\n\n")
        
        # Write BRACKET_SLOTS
        out.write("BRACKET_SLOTS = {\n")
        for slot in sorted_slots:
            out.write(f"    {slot['id']}: {repr(slot)},\n")
        out.write("}\n")

    print(f"Static data file written successfully to: {output_path}")

if __name__ == "__main__":
    main()

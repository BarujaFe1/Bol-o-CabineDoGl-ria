import streamlit as st

def get_theme_css(theme_mode: str) -> str:
    # Definir os tokens de estilo para cada modo
    light_vars = """
  --bg: #F5EBDD;
  --bg-soft: #FDF9F3;
  --panel: #FFFDF8;
  --panel-strong: #ffffff;
  --surface: #FFFDF8;
  --surface-elevated: #ffffff;
  --ink: #0A211B;
  --muted: #66736D;
  --green: #176B4D;
  --green-hover: #0F5A3F;
  --green-2: #0B3328;
  --gold: #D8A94A;
  --gold-bg: #FFF3CC;
  --red: #B42318;
  --red-bg: #FDE7E3;
  --blue-bg: #DCEEFF;
  --green-bg: #DFF5E8;
  --line: rgba(11, 51, 40, 0.12);
  --shadow: 0 16px 48px rgba(11, 51, 40, 0.08);
  --shadow-hover: 0 24px 64px rgba(11, 51, 40, 0.14);
  --grad-bg: radial-gradient(circle at 10% 8%, rgba(216, 169, 74, 0.18), transparent 30%),
             radial-gradient(circle at 90% 15%, rgba(23, 107, 77, 0.15), transparent 35%),
             linear-gradient(180deg, #FDF9F3 0%, #F5EBDD 100%);
    """

    dark_vars = """
  --bg: #061713;
  --bg-soft: #0B241F;
  --panel: #102E27;
  --panel-strong: #14382F;
  --surface: #102E27;
  --surface-elevated: #14382F;
  --ink: #F8F2E4;
  --muted: #B8C8BF;
  --green: #2DD67B;
  --green-hover: #22A45C;
  --green-2: #176B4D;
  --gold: #D8A94A;
  --gold-bg: rgba(216, 169, 74, 0.15);
  --red: #FF6B5A;
  --red-bg: rgba(255, 107, 90, 0.15);
  --blue-bg: rgba(45, 156, 219, 0.15);
  --green-bg: rgba(45, 214, 123, 0.15);
  --line: rgba(255, 255, 255, 0.08);
  --shadow: 0 16px 48px rgba(0, 0, 0, 0.4);
  --shadow-hover: 0 24px 64px rgba(0, 0, 0, 0.55);
  --grad-bg: radial-gradient(circle at 10% 8%, rgba(216, 169, 74, 0.15), transparent 30%),
             radial-gradient(circle at 90% 15%, rgba(45, 214, 123, 0.1), transparent 35%),
             linear-gradient(180deg, #0B241F 0%, #061713 100%);
    """

    # Seletor baseado no tema
    vars_block = ""
    if theme_mode == "light":
        vars_block = f":root {{ {light_vars} }}"
    elif theme_mode == "dark":
        vars_block = f":root {{ {dark_vars} }}"
    else:  # system
        vars_block = f"""
        :root {{ {light_vars} }}
        @media (prefers-color-scheme: dark) {{
            :root {{ {dark_vars} }}
        }}
        """

    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Outfit:wght@300;400;500;600;700;800;900&display=swap');

{vars_block}

/* Aplicar tipografia premium de forma global */
html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
  font-family: 'Outfit', 'Inter', sans-serif !important;
}}

/* Forçar fundos e textos */
[data-testid="stAppViewContainer"] {{
  background: var(--grad-bg) !important;
  color: var(--ink) !important;
  transition: background 0.3s ease, color 0.3s ease;
}}

[data-testid="stHeader"] {{ 
  background: transparent !important; 
}}

[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #0B3328, #07221A 70%, #030F0C) !important;
  border-right: 1px solid rgba(255,255,255,0.05);
}}

/* Sidebar text override */
[data-testid="stSidebar"] .stMarkdown, 
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] h1, 
[data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3, 
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stRadio"] p,
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
  color: #F8F2E4 !important; 
}}

.block-container {{ 
  padding-top: 2rem; 
  padding-bottom: 3rem; 
  max-width: 1200px; 
}}

/* Customização de scrollbars */
::-webkit-scrollbar {{
  width: 8px;
  height: 8px;
}}
::-webkit-scrollbar-track {{
  background: var(--bg);
}}
::-webkit-scrollbar-thumb {{
  background: var(--line);
  border-radius: 4px;
}}
::-webkit-scrollbar-thumb:hover {{
  background: var(--muted);
}}

/* Ocultar elementos padrão do Streamlit de forma limpa */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ visibility: hidden; }}

/* Hero Premium */
.copa-hero {{
  border: 1px solid var(--line);
  background: linear-gradient(135deg, var(--panel-strong) 0%, var(--panel) 100%);
  border-radius: 28px;
  padding: 32px 40px;
  box-shadow: var(--shadow);
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
  border-left: 6px solid var(--green);
}}

.copa-hero::after {{
  content: "🏆";
  position: absolute;
  right: 20px;
  bottom: 0px;
  font-size: 150px;
  opacity: 0.04;
  pointer-events: none;
}}

.eyebrow {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--green-bg);
  color: var(--green);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}}

.copa-title {{
  color: var(--ink);
  font-size: clamp(32px, 4.5vw, 56px);
  line-height: 1.05;
  font-weight: 900;
  letter-spacing: -1.5px;
  margin: 14px 0 8px;
}}

.copa-subtitle {{
  color: var(--muted);
  font-size: 17px;
  max-width: 820px;
  line-height: 1.5;
  margin-bottom: 0;
}}

.page-header {{
  margin-bottom: 24px;
}}

.page-title {{
  color: var(--ink);
  font-weight: 900;
  font-size: 28px;
  letter-spacing: -0.5px;
}}

.page-subtitle {{
  color: var(--muted);
  font-size: 15px;
}}

/* Cards & Layout */
.card {{
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 20px;
  padding: 24px;
  box-shadow: var(--shadow);
  margin-bottom: 20px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.card:hover {{
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}}

.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin: 16px 0 24px;
}}

.kpi {{
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 20px;
  padding: 20px;
  box-shadow: var(--shadow);
  border-bottom: 4px solid var(--green);
  transition: transform 0.2s ease;
}}

.kpi:hover {{
  transform: translateY(-2px);
}}

.kpi .label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 800;
  color: var(--muted);
}}

.kpi .value {{
  font-size: 28px;
  font-weight: 900;
  color: var(--ink);
  margin-top: 4px;
}}

.step-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin: 20px 0;
}}

.step {{
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 20px;
  min-height: 150px;
  box-shadow: var(--shadow);
  transition: transform 0.2s ease;
}}

.step:hover {{
  transform: translateY(-2px);
}}

.step .num {{
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--green);
  color: white;
  font-weight: 900;
  margin-bottom: 12px;
}}

.step h4 {{ 
  margin: 0 0 6px; 
  color: var(--ink); 
  font-weight: 800;
}}

.step p {{ 
  color: var(--muted); 
  font-size: 14px; 
  margin: 0; 
  line-height: 1.4; 
}}

/* Callouts & Alerts */
.callout {{
  border-radius: 16px;
  padding: 16px 20px;
  margin: 16px 0;
  border-left: 5px solid transparent;
  box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}}

.callout.info {{
  background: var(--blue-bg);
  border-color: #2D9CDB;
  color: var(--ink);
}}

.callout.success {{
  background: var(--green-bg);
  border-color: var(--green);
  color: var(--ink);
}}

.callout.warning {{
  background: var(--gold-bg);
  border-color: var(--gold);
  color: var(--ink);
}}

.callout.error {{
  background: var(--red-bg);
  border-color: var(--red);
  color: var(--ink);
}}

/* Empty States */
.empty-state {{
  text-align: center;
  padding: 40px 24px;
  border: 2px dashed var(--line);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.02);
  margin: 20px 0;
}}

.empty-state .icon {{
  font-size: 48px;
  margin-bottom: 12px;
}}

.empty-state h3 {{
  margin: 0 0 6px;
  color: var(--ink);
  font-weight: 800;
}}

.empty-state p {{
  color: var(--muted);
  font-size: 15px;
  margin: 0 auto 16px;
  max-width: 480px;
}}

/* Podium & Ranking Styles */
.podium {{
  display: grid;
  grid-template-columns: 1fr 1.15fr 1fr;
  gap: 16px;
  align-items: end;
  margin: 24px 0 32px;
}}

.podium-card {{
  border: 1px solid var(--line);
  background: linear-gradient(180deg, var(--panel-strong), var(--panel));
  border-radius: 24px;
  padding: 20px;
  text-align: center;
  box-shadow: var(--shadow);
}}

.podium-card.first {{
  padding: 32px 24px;
  transform: translateY(-12px);
  border-color: rgba(216, 169, 74, 0.5);
  background: linear-gradient(180deg, var(--panel-strong), var(--gold-bg));
  box-shadow: 0 20px 50px rgba(216,169,74,0.18);
}}

.podium-card.second {{
  border-color: rgba(180, 180, 180, 0.3);
}}

.podium-card.third {{
  border-color: rgba(196, 126, 60, 0.25);
}}

.medal {{ 
  font-size: 40px; 
  margin-bottom: 4px; 
}}

.podium-rank {{ 
  font-size: 11px; 
  font-weight: 800; 
  letter-spacing: .06em; 
  text-transform: uppercase; 
  color: var(--gold); 
}}

.podium-name {{ 
  color: var(--ink); 
  font-size: 22px; 
  font-weight: 900; 
  margin-top: 6px; 
}}

.podium-points {{ 
  color: var(--green); 
  font-size: 30px; 
  font-weight: 950; 
  margin-top: 6px; 
}}

.podium-note {{ 
  color: var(--muted); 
  font-size: 13px; 
  margin-top: 6px; 
}}

/* Badges */
.badge {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 99px;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 4px 4px 0;
  border: 1px solid var(--line);
}}

.badge.neutral {{
  background-color: var(--bg);
  color: var(--muted);
}}
.badge.success {{
  background-color: var(--green-bg);
  color: var(--green);
}}
.badge.warning {{
  background-color: var(--gold-bg);
  color: var(--gold);
}}
.badge.error {{
  background-color: var(--red-bg);
  color: var(--red);
}}
.badge.info {{
  background-color: var(--blue-bg);
  color: var(--ink);
}}

.success-card {{
  border-radius: 24px;
  padding: 24px;
  background: linear-gradient(135deg, var(--green-bg), var(--gold-bg));
  border: 1px solid var(--line);
  text-align: center;
}}

.success-card h3 {{
  color: var(--ink);
  font-weight: 900;
  margin-top: 0;
}}

.success-card h2 {{
  font-size: 36px;
  font-weight: 950;
  color: var(--green);
  margin: 12px 0;
  letter-spacing: 1px;
}}

.warn-box {{
  border: 1px solid var(--line);
  background: var(--gold-bg);
  border-radius: 16px;
  padding: 12px 16px;
  color: var(--ink);
  margin: 8px 0;
  font-size: 14px;
}}

.error-box {{
  border: 1px solid var(--line);
  background: var(--red-bg);
  border-radius: 16px;
  padding: 12px 16px;
  color: var(--ink);
  margin: 8px 0;
  font-size: 14px;
}}

.small-muted {{ 
  color: var(--muted); 
  font-size: 14px; 
  line-height: 1.4; 
}}

/* Button & Scroll for Mobile & Premium Tables */
div[data-testid="stDataFrame"] {
  border: 1px solid var(--line) !important;
  border-radius: 16px !important;
  overflow: hidden !important;
  background-color: var(--panel) !important;
  box-shadow: var(--shadow) !important;
}

.match-card {
  border: 1px solid var(--line);
  background: linear-gradient(135deg, var(--panel-strong) 0%, var(--panel) 100%);
  border-radius: 20px;
  padding: 20px;
  box-shadow: var(--shadow);
  margin-bottom: 16px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.match-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}

@media (max-width: 768px) {{
  .kpi-grid, .step-grid, .podium {{ 
    grid-template-columns: 1fr; 
  }}
  .podium-card.first {{ 
    transform: none; 
  }}
  .copa-hero {{ 
    padding: 24px; 
    border-radius: 20px; 
  }}
  .block-container {{
    padding-left: 10px;
    padding-right: 10px;
  }}
  .stButton > button {
    width: 100% !important;
  }
}}

/* Step Indicator */
.step-indicator {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin: 20px 0 28px;
  padding: 0 10px;
}}
.step-item {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}}
.step-dot {{
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800;
  border: 2px solid var(--line);
  background: var(--panel); color: var(--muted);
  transition: all 0.2s ease;
}}
.step-dot.active {{
  background: var(--green); color: white; border-color: var(--green);
  box-shadow: 0 4px 12px var(--green-bg);
}}
.step-dot.done {{
  background: var(--green-bg); color: var(--green); border-color: var(--green);
}}
.step-label {{
  font-size: 10px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: 0.3px;
  white-space: nowrap;
}}
.step-dot.active + .step-label {{
  color: var(--ink);
}}
.step-line {{
  flex: 1; height: 2px; background: var(--line);
  margin: 0 4px; margin-bottom: 24px; min-width: 12px;
  transition: background 0.2s ease;
}}
.step-line.done {{
  background: var(--green);
}}
</style>
    """
    return css

def inject_css() -> None:
    # Get active theme from session_state, default to system
    theme_mode = st.session_state.get("theme_mode", "system")
    css = get_theme_css(theme_mode)
    st.markdown(css, unsafe_allow_html=True)

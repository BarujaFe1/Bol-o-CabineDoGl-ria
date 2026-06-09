import streamlit as st

APP_CSS = """
<style>
:root {
  --bg: #F5EBDD;
  --panel: #FFFDF8;
  --panel-strong: #ffffff;
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
}

[data-testid="stAppViewContainer"] {
  background:
    radial-gradient(circle at 10% 8%, rgba(216, 169, 74, 0.18), transparent 30%),
    radial-gradient(circle at 90% 15%, rgba(23, 107, 77, 0.15), transparent 35%),
    linear-gradient(180deg, #FDF9F3 0%, #F5EBDD 100%);
}

[data-testid="stHeader"] { 
  background: transparent; 
}

[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0B3328, #102d24 70%, #061914);
}

[data-testid="stSidebar"] * { 
  color: #FFFDF8 !important; 
}

.block-container { 
  padding-top: 1.5rem; 
  padding-bottom: 2rem; 
  max-width: 1200px; 
}

/* Hide default Streamlit elements safely */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* Custom Hero Layout */
.copa-hero {
  border: 1px solid var(--line);
  background:
    linear-gradient(135deg, rgba(255,253,248,0.95), rgba(255,250,240,0.85)),
    radial-gradient(circle at 95% 20%, rgba(216,169,74,0.18), transparent 30%);
  border-radius: 28px;
  padding: 32px 40px;
  box-shadow: var(--shadow);
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
  border-left: 6px solid var(--green);
}

.copa-hero::after {
  content: "🏆";
  position: absolute;
  right: 20px;
  bottom: 0px;
  font-size: 150px;
  opacity: 0.06;
  pointer-events: none;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(23, 107, 77, 0.09);
  color: var(--green);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.copa-title {
  color: var(--ink);
  font-size: clamp(32px, 4.5vw, 56px);
  line-height: 1.05;
  font-weight: 900;
  letter-spacing: -1.5px;
  margin: 14px 0 8px;
}

.copa-subtitle {
  color: var(--muted);
  font-size: 17px;
  max-width: 820px;
  line-height: 1.5;
  margin-bottom: 0;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  color: var(--ink);
  font-weight: 900;
  font-size: 28px;
  letter-spacing: -0.5px;
}

.page-subtitle {
  color: var(--muted);
  font-size: 15px;
}

/* Cards & Layout */
.card {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 20px;
  padding: 24px;
  box-shadow: var(--shadow);
  margin-bottom: 20px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin: 16px 0 24px;
}

.kpi {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 20px;
  padding: 20px;
  box-shadow: var(--shadow);
  border-bottom: 4px solid var(--green);
  transition: transform 0.2s ease;
}

.kpi:hover {
  transform: translateY(-2px);
}

.kpi .label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 800;
  color: var(--muted);
}

.kpi .value {
  font-size: 28px;
  font-weight: 900;
  color: var(--ink);
  margin-top: 4px;
}

.step-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin: 20px 0;
}

.step {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 20px;
  padding: 20px;
  min-height: 150px;
  box-shadow: var(--shadow);
  transition: transform 0.2s ease;
}

.step:hover {
  transform: translateY(-2px);
}

.step .num {
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
}

.step h4 { 
  margin: 0 0 6px; 
  color: var(--ink); 
  font-weight: 800;
}

.step p { 
  color: var(--muted); 
  font-size: 14px; 
  margin: 0; 
  line-height: 1.4; 
}

/* Callouts & Alerts */
.callout {
  border-radius: 16px;
  padding: 16px 20px;
  margin: 16px 0;
  border-left: 5px solid transparent;
  box-shadow: 0 4px 12px rgba(0,0,0,0.02);
}

.callout.info {
  background: var(--blue-bg);
  border-color: #2D9CDB;
  color: #1F6E96;
}

.callout.success {
  background: var(--green-bg);
  border-color: var(--green);
  color: #0E4E35;
}

.callout.warning {
  background: var(--gold-bg);
  border-color: var(--gold);
  color: #72541A;
}

.callout.error {
  background: var(--red-bg);
  border-color: var(--red);
  color: #8C211A;
}

/* Empty States */
.empty-state {
  text-align: center;
  padding: 40px 24px;
  border: 2px dashed var(--line);
  border-radius: 24px;
  background: rgba(255,253,248,0.5);
  margin: 20px 0;
}

.empty-state .icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.empty-state h3 {
  margin: 0 0 6px;
  color: var(--ink);
  font-weight: 800;
}

.empty-state p {
  color: var(--muted);
  font-size: 15px;
  margin: 0 auto 16px;
  max-width: 480px;
}

/* Podium & Ranking Styles */
.podium {
  display: grid;
  grid-template-columns: 1fr 1.15fr 1fr;
  gap: 16px;
  align-items: end;
  margin: 24px 0 32px;
}

.podium-card {
  border: 1px solid var(--line);
  background: linear-gradient(180deg, #ffffff, #FFFDF8);
  border-radius: 24px;
  padding: 20px;
  text-align: center;
  box-shadow: var(--shadow);
}

.podium-card.first {
  padding: 32px 24px;
  transform: translateY(-12px);
  border-color: rgba(216, 169, 74, 0.4);
  background: linear-gradient(180deg, #ffffff, #FFF8E7);
  box-shadow: 0 20px 50px rgba(216,169,74,0.18);
}

.podium-card.second {
  border-color: rgba(180, 180, 180, 0.3);
}

.podium-card.third {
  border-color: rgba(196, 126, 60, 0.25);
}

.medal { 
  font-size: 40px; 
  margin-bottom: 4px; 
}

.podium-rank { 
  font-size: 11px; 
  font-weight: 800; 
  letter-spacing: .06em; 
  text-transform: uppercase; 
  color: var(--gold); 
}

.podium-name { 
  color: var(--ink); 
  font-size: 22px; 
  font-weight: 900; 
  margin-top: 6px; 
}

.podium-points { 
  color: var(--green); 
  font-size: 30px; 
  font-weight: 950; 
  margin-top: 6px; 
}

.podium-note { 
  color: var(--muted); 
  font-size: 13px; 
  margin-top: 6px; 
}

/* Badges & Tables */
.badge {
  display: inline-flex;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--panel-strong);
  padding: 4px 10px;
  color: var(--ink);
  font-size: 11px;
  font-weight: 800;
  margin: 0 4px 4px 0;
  text-transform: uppercase;
}

.badge.gold {
  background: var(--gold-bg);
  border-color: rgba(216, 169, 74, 0.4);
  color: #72541A;
}

.badge.silver {
  background: #F2F2F2;
  border-color: rgba(180, 180, 180, 0.4);
  color: #555555;
}

.badge.bronze {
  background: #FDF1E6;
  border-color: rgba(196, 126, 60, 0.3);
  color: #9C5212;
}

.badge.green {
  background: var(--green-bg);
  border-color: rgba(23, 107, 77, 0.3);
  color: #0E4E35;
}

.badge.red {
  background: var(--red-bg);
  border-color: rgba(180, 35, 24, 0.3);
  color: #8C211A;
}

.badge.blue {
  background: var(--blue-bg);
  border-color: rgba(45, 156, 219, 0.3);
  color: #1F6E96;
}

.success-card {
  border-radius: 24px;
  padding: 24px;
  background: linear-gradient(135deg, rgba(23, 107, 77, 0.12), rgba(216, 169, 74, 0.15));
  border: 1px solid rgba(23, 107, 77, 0.2);
  text-align: center;
}

.success-card h3 {
  color: var(--green-2);
  font-weight: 900;
  margin-top: 0;
}

.success-card h2 {
  font-size: 36px;
  font-weight: 950;
  color: var(--green);
  margin: 12px 0;
  letter-spacing: 1px;
}

.warn-box {
  border: 1px solid rgba(216, 169, 74, 0.3);
  background: var(--gold-bg);
  border-radius: 16px;
  padding: 12px 16px;
  color: #72541A;
  margin: 8px 0;
  font-size: 14px;
}

.error-box {
  border: 1px solid rgba(180, 35, 24, 0.25);
  background: var(--red-bg);
  border-radius: 16px;
  padding: 12px 16px;
  color: #8C211A;
  margin: 8px 0;
  font-size: 14px;
}

.small-muted { 
  color: var(--muted); 
  font-size: 14px; 
  line-height: 1.4; 
}

.badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 99px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-left: 5px;
}
.badge.neutral {
  background-color: #F5EBDD;
  color: #66736D;
  border: 1px solid #E6D2B5;
}
.badge.success {
  background-color: #DFF5E8;
  color: #0B3328;
  border: 1px solid rgba(23, 107, 77, 0.2);
}
.badge.warning {
  background-color: #FFF3CC;
  color: #72541A;
  border: 1px solid rgba(216, 169, 74, 0.2);
}
.badge.error {
  background-color: #FDE7E3;
  color: #B42318;
  border: 1px solid rgba(180, 35, 24, 0.2);
}
.badge.info {
  background-color: #DCEEFF;
  color: #1F6E96;
  border: 1px solid rgba(45, 156, 219, 0.2);
}

/* Button & Scroll for Mobile */
@media (max-width: 768px) {
  .kpi-grid, .step-grid, .podium { 
    grid-template-columns: 1fr; 
  }
  .podium-card.first { 
    transform: none; 
  }
  .copa-hero { 
    padding: 24px; 
    border-radius: 20px; 
  }
  .block-container {
    padding-left: 10px;
    padding-right: 10px;
  }
  .step-label { font-size: 8px; }
  .step-dot { width: 26px; height: 26px; font-size: 11px; }
}

/* Step Indicator */
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin: 20px 0 28px;
  padding: 0 10px;
}
.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.step-dot {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800;
  border: 2px solid rgba(11, 51, 40, 0.15);
  background: #FFFDF8; color: #66736D;
  transition: all 0.2s ease;
}
.step-dot.active {
  background: #176B4D; color: white; border-color: #176B4D;
  box-shadow: 0 4px 12px rgba(23, 107, 77, 0.3);
}
.step-dot.done {
  background: #DFF5E8; color: #0B3328; border-color: rgba(23, 107, 77, 0.3);
}
.step-label {
  font-size: 10px; font-weight: 700; color: #66736D;
  text-transform: uppercase; letter-spacing: 0.3px;
  white-space: nowrap;
}
.step-dot.active + .step-label {
  color: #0B3328;
}
.step-line {
  flex: 1; height: 2px; background: rgba(11, 51, 40, 0.1);
  margin: 0 4px; margin-bottom: 24px; min-width: 12px;
  transition: background 0.2s ease;
}
.step-line.done {
  background: rgba(23, 107, 77, 0.3);
}
</style>
"""

def inject_css() -> None:
    st.markdown(APP_CSS, unsafe_allow_html=True)

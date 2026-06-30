import json
import os
import matplotlib.pyplot as plt
import pandas as pd

HISTORY_FILE = "history.json"
PORTFOLIO_FILE = "portfolio.json"

def generate_charts():
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except:
                pass
            
    if not history:
        dates = []
        daily_gains = {}
        benchmark_gains = {}
    else:
        # Aggréger par date d'évaluation
        daily_gains = {}
        benchmark_gains = {}
        
        for entry in history:
            date = entry.get("eval_date")
            if not date:
                continue
                
            if date not in daily_gains:
                daily_gains[date] = {"09:00": 0, "09:30": 0, "12:00": 0, "17:00": 0}
                benchmark_gains[date] = {"09:00": 0, "09:30": 0, "12:00": 0, "17:00": 0}
                
            perf = entry.get("performance", {})
            bench_perf = entry.get("benchmark_performance", {})
            
            for time_key in ["09:00", "09:30", "12:00", "17:00"]:
                # On additionne les gains/pertes en euros pour le bot
                p = perf.get(time_key)
                if p and isinstance(p, dict):
                    daily_gains[date][time_key] += p.get("gain_loss_eur", 0)
                    
                # Pour le benchmark, on prend la performance moyenne ou totale.
                b = bench_perf.get(time_key)
                if b and isinstance(b, dict):
                    benchmark_gains[date][time_key] += b.get("gain_loss_eur", 0)
                
    dates = sorted(list(daily_gains.keys()))
        
    # Calcul des cumuls
    times = ["09:00", "09:30", "12:00", "17:00"]
    cum_bot = {t: [0] for t in times}
    cum_bench = {t: [0] for t in times}
    
    for d in dates:
        for t in times:
            cum_bot[t].append(cum_bot[t][-1] + daily_gains[d][t])
            cum_bench[t].append(cum_bench[t][-1] + benchmark_gains[d][t])
            
    # dates_x = ['Départ'] + dates
    dates_x = [''] + [d[5:] for d in dates] # MM-DD
    
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Performance Cumulée (Bot vs ETF CAC 40) en Euros', fontsize=16)
    
    axes = axs.flatten()
    for i, t in enumerate(times):
        ax = axes[i]
        ax.plot(dates_x, cum_bot[t], label='Trading Bot IA', marker='o', color='royalblue', linewidth=2)
        ax.plot(dates_x, cum_bench[t], label='ETF CAC 40', marker='x', color='darkorange', linewidth=2, linestyle='--')
        ax.set_title(f'Revente à {t}')
        ax.set_ylabel('Gains/Pertes Cumulés (€)')
        ax.legend()
        ax.grid(True, linestyle=':', alpha=0.7)
        ax.tick_params(axis='x', rotation=45)
        
    plt.tight_layout()
    plt.savefig('performance_chart.png')
    plt.close()

def generate_markdown_report():
    if not os.path.exists(PORTFOLIO_FILE):
        return
    with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        try:
            portfolio = json.load(f)
        except:
            portfolio = []
            
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except:
                history = []
    else:
        history = []
        
    report = "# 📊 Rapport Journalier du Trading Bot\n\n"
    
    report += "## 🛒 Achats du Jour (Positions Actuelles)\n"
    if not portfolio:
        report += "*Aucune position prise aujourd'hui (marché trop incertain ou données non disponibles).* \n"
    else:
        for p in portfolio:
            report += f"### {p['company']} ({p['ticker']})\n"
            report += f"- **Achat :** {p['buy_price']}€ (pour 500€)\n"
            report += f"- **Analyse de l'IA :** {p['reason']}\n\n"
            
    report += "---\n\n"
    report += "## 📈 Performances Récentes\n"
    
    # Prendre les 4 dernières évaluations
    recent_history = history[-4:] if history else []
    if recent_history:
        for h in reversed(recent_history):
            perf = h.get("performance", {})
            p_930 = perf.get("09:30")
            if p_930:
                gain_eur = p_930.get("gain_loss_eur", 0)
                sign = "+" if gain_eur >= 0 else ""
                report += f"- **{h['eval_date']}** | {h['company']} ({h['ticker']}) : {sign}{gain_eur}€ (à 09h30)\n"
            else:
                report += f"- **{h['eval_date']}** | {h['company']} ({h['ticker']}) : En attente de cotation\n"
    else:
        report += "*Pas d'historique suffisant.* \n"
        
    report += "\n---\n*Ce rapport est généré automatiquement par l'IA Gemini.*"
    
    with open("daily_report.md", "w", encoding="utf-8") as f:
        f.write(report)

if __name__ == "__main__":
    generate_charts()
    generate_markdown_report()

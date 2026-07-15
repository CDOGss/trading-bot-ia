import os
import json
import datetime
import pytz
import yfinance as yf
import feedparser
from google import genai
from google.genai import types
import report

# Configurations
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "history.json"

# Flux RSS pour l'actualité financière française et internationale
RSS_FEEDS = [
    "https://www.lesechos.fr/rss/bourse",
    "https://www.boursorama.com/rss/actualites.xml",
    "https://news.google.com/rss/search?q=CAC+40+bourse+when:1d&hl=fr&gl=FR&ceid=FR:fr",
    "https://news.google.com/rss/search?q=Wall+Street+bourse+when:1d&hl=fr&gl=FR&ceid=FR:fr", # Tendance Wall Street
    "https://news.google.com/rss/search?q=macroéconomie+taux+BCE+FED+when:1d&hl=fr&gl=FR&ceid=FR:fr" # Macro et Banques Centrales
]

def load_json(filepath, default_value):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_value
    return default_value

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_intraday_prices(ticker_symbol, date_str):
    """
    Récupère les prix à 09:00, 09:30, 12:00 et 17:00 pour une date donnée.
    """
    ticker = yf.Ticker(ticker_symbol)
    # On récupère les données des 5 derniers jours par pas de 5 minutes
    df = ticker.history(interval="5m", period="5d")
    
    paris_tz = pytz.timezone('Europe/Paris')
    
    prices = {
        "09:00": None,
        "09:30": None,
        "12:00": None,
        "17:00": None
    }
    
    if df.empty:
        return prices
        
    def get_closest_price(target_hour, target_minute):
        best_diff = None
        best_price = None
        for dt, row in df.iterrows():
            dt_paris = dt.astimezone(paris_tz)
            if dt_paris.strftime('%Y-%m-%d') == date_str:
                diff = abs((dt_paris.hour * 60 + dt_paris.minute) - (target_hour * 60 + target_minute))
                # On tolère une différence de 15 minutes max
                if best_diff is None or diff < best_diff:
                    if diff <= 15:
                        best_diff = diff
                        best_price = row['Close']
        return best_price

    prices["09:00"] = get_closest_price(9, 0)
    prices["09:30"] = get_closest_price(9, 30)
    prices["12:00"] = get_closest_price(12, 0)
    prices["17:00"] = get_closest_price(17, 0)
    
    return prices

def evaluate_portfolio():
    """Évalue le portefeuille de la veille et enregistre les performances."""
    portfolio = load_json(PORTFOLIO_FILE, [])
    if not portfolio:
        print("Aucun portefeuille actif à évaluer.")
        return

    history = load_json(HISTORY_FILE, [])
    paris_tz = pytz.timezone('Europe/Paris')
    today_str = datetime.datetime.now(paris_tz).strftime('%Y-%m-%d')
    
    # Pre-fetch benchmark prices
    if portfolio:
        # Assuming all portfolio entries have the same buy_date (which they should)
        buy_date = portfolio[0]['buy_date']
        bench_prices_buy_day = get_intraday_prices("^FCHI", buy_date)
        bench_buy_price = bench_prices_buy_day.get("17:00")
        bench_prices_today = get_intraday_prices("^FCHI", today_str)

    for position in portfolio:
        ticker = position['ticker']
        buy_price = position['buy_price']
        buy_date = position['buy_date']
        
        print(f"Évaluation de {ticker} acheté à {buy_price}€ le {buy_date}")
        prices_today = get_intraday_prices(ticker, today_str)
        
        performance = {}
        for time_key, current_price in prices_today.items():
            if current_price:
                perf_pct = ((current_price - buy_price) / buy_price) * 100
                perf_eur = (position['amount_eur'] / buy_price) * (current_price - buy_price)
                performance[time_key] = {
                    "price": current_price,
                    "gain_loss_pct": round(perf_pct, 2),
                    "gain_loss_eur": round(perf_eur, 2)
                }
            else:
                performance[time_key] = None
                
        benchmark_performance = {}
        if bench_buy_price:
            for time_key, current_bench_price in bench_prices_today.items():
                if current_bench_price:
                    b_perf_pct = ((current_bench_price - bench_buy_price) / bench_buy_price) * 100
                    b_perf_eur = (position['amount_eur'] / bench_buy_price) * (current_bench_price - bench_buy_price)
                    benchmark_performance[time_key] = {
                        "price": current_bench_price,
                        "gain_loss_pct": round(b_perf_pct, 2),
                        "gain_loss_eur": round(b_perf_eur, 2)
                    }
                else:
                    benchmark_performance[time_key] = None

        history_entry = {
            "ticker": ticker,
            "company": position.get('company', ''),
            "buy_date": buy_date,
            "buy_price": buy_price,
            "conviction": position.get('conviction'),
            "market_regime": position.get('market_regime'),
            "eval_date": today_str,
            "performance": performance,
            "benchmark_performance": benchmark_performance
        }
        history.append(history_entry)
        
    save_json(HISTORY_FILE, history)
    # Réinitialisation du portefeuille après revente virtuelle
    save_json(PORTFOLIO_FILE, [])
    print("Évaluation terminée. Historique mis à jour.")

def fetch_news():
    """Récupère les actualités via flux RSS."""
    news_items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:8]: # Top 8 par flux pour ne pas saturer le contexte
                news_items.append(f"Titre: {entry.title}\nLien: {entry.link}\n")
        except Exception as e:
            print(f"Erreur lors de la lecture du flux {feed_url} : {e}")
    return "\n".join(news_items)

def fetch_market_data():
    """Snapshot chiffré des indices : le prompt vantait 'l'avantage Wall Street'
    mais l'IA ne voyait que des titres RSS, aucun prix réel."""
    indices = [("^FCHI", "CAC 40"), ("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^VIX", "VIX (volatilité)")]
    lines = []
    for symbol, name in indices:
        try:
            t = yf.Ticker(symbol)
            daily = t.history(period="2d", interval="1d")
            intra = t.history(period="1d", interval="5m")
            if daily.empty:
                continue
            prev_close = daily['Close'].iloc[0] if len(daily) > 1 else daily['Close'].iloc[-1]
            # Certains indices (ex : ^VIX) n'ont pas d'intraday sur yfinance :
            # on retombe sur la dernière cotation quotidienne.
            last = float(intra['Close'].iloc[-1]) if not intra.empty else float(daily['Close'].iloc[-1])
            chg = (last - prev_close) / prev_close * 100
            lines.append(f"- {name} : {last:.2f} ({chg:+.2f}% vs clôture de la veille)")
        except Exception as e:
            print(f"Donnée marché indisponible pour {symbol} : {e}")
    return "\n".join(lines) if lines else "Données de marché indisponibles."

def build_feedback(n=5):
    """Résultats des n dernières sélections (revente à l'ouverture), pour que
    l'IA voie ce que ses choix ont réellement donné."""
    history = load_json(HISTORY_FILE, [])
    entries = [e for e in history
               if isinstance((e.get('performance') or {}).get('09:00'), dict)][-n:]
    if not entries:
        return "Aucun historique disponible (premières séances)."
    lines = []
    for e in entries:
        p = e['performance']['09:00']
        b = (e.get('benchmark_performance') or {}).get('09:00')
        bench = f" (CAC 40 : {b['gain_loss_pct']:+.2f}%)" if isinstance(b, dict) else ""
        lines.append(f"- {e['buy_date']} {e['company']} ({e['ticker']}) : {p['gain_loss_pct']:+.2f}% à l'ouverture du lendemain{bench}")
    return "\n".join(lines)

def analyze_and_buy():
    """Analyse l'actualité avec Gemini et simule un achat."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Erreur : La variable d'environnement GEMINI_API_KEY n'est pas définie.")
        return

    print("Récupération de l'actualité...")
    news_text = fetch_news()
    print("Récupération des données de marché...")
    market_data = fetch_market_data()
    feedback = build_feedback()
    
    print("Analyse par l'IA (Gemini)...")
    client = genai.Client(api_key=api_key)
    
    prompt = f"""
Tu es un gérant de portefeuille "Senior" institutionnel et un trader d'élite spécialisé sur le marché européen (CAC 40 et SBF 120). Ton objectif absolu est de surperformer le benchmark (ETF CAC 40).
Tu interviens en fin de séance européenne (17h00 heure de Paris). À cette heure, Wall Street est déjà ouvert depuis 1h30, ce qui te donne un avantage décisif sur la direction globale du marché.

RÈGLE DE SORTIE IMPÉRATIVE : toute position achetée maintenant sera revendue demain matin à 09h00 précises, à l'ouverture de la Bourse de Paris. Tu optimises donc EXCLUSIVEMENT pour le gap d'ouverture (overnight), pas pour la performance en séance. L'historique montre que les gains se font à l'ouverture puis s'érodent en séance : seul le gap compte.

Données de marché en temps réel (source Yahoo Finance) :
{market_data}

Résultats de tes dernières sélections (revente à l'ouverture du lendemain) — tires-en les leçons :
{feedback}

Voici le flux brut des actualités financières du jour (Europe, Wall Street, Macroéconomie) :
{news_text}

Ta mission :
1. Analyser le sentiment global du marché (Risk-on / Risk-off) à partir des données chiffrées ci-dessus ET de l'actualité.
2. Prendre en compte la dynamique en cours à Wall Street (qui dictera souvent la tendance de l'ouverture européenne demain à 9h00).
3. Identifier les catalyseurs qui NE SONT PAS ENCORE DANS LE PRIX : c'est ton seul véritable edge. Privilégie les informations apparues en toute fin de séance européenne ou pendant la séance américaine (après ~16h00 à Paris). Un catalyseur connu depuis ce matin est déjà intégré dans le cours de clôture de Paris — il ne produira AUCUN gap demain.
4. PIÈGES À ÉVITER impérativement (gaps mécaniques ou aléatoires, sans edge) :
   - une valeur qui détache un dividende demain : gap baissier mécanique du montant du dividende ;
   - une valeur qui publie ses résultats demain avant l'ouverture : loterie binaire, pas un edge ;
   - courir après une valeur qui a déjà fortement monté aujourd'hui sur un catalyseur connu de tous : tu achèterais le sommet.
5. Sélectionner 0, 1 ou 2 actions maximum (CAC 40 ou SBF 120) présentant un excellent ratio risque/rendement pour le gap de demain 09h00, chacune notée d'une conviction de 1 à 10 :
   - N'achète JAMAIS une valeur dont ta conviction est inférieure à 7/10.
   - Ne propose 2 valeurs que si les DEUX sont à 8/10 ou plus. Une seule excellente idée vaut mieux que deux idées moyennes.
   - Si le marché est trop incertain (Risk-off marqué, forte baisse de Wall Street en cours), ton devoir de gérant est de préserver le capital : renvoie une liste vide.
   - Ne force jamais un achat si tu n'es pas convaincu.

Renvoie ta réponse au format JSON avec :
- "market_regime": "risk_on", "neutre" ou "risk_off" (ton diagnostic global)
- "picks": liste de 0 à 2 objets contenant :
  - "company": le nom de l'entreprise
  - "ticker": le symbole Yahoo Finance exact (doit impérativement se terminer par .PA, ex: "OR.PA" pour L'Oréal)
  - "conviction": ta note de 1 à 10 (jamais d'achat sous 7)
  - "reason": ton analyse macro/micro, en précisant POURQUOI le catalyseur n'est pas encore dans le prix.

Exemple si tu trouves une excellente opportunité :
{{
  "market_regime": "risk_on",
  "picks": [
    {{"company": "Nom Entreprise 1", "ticker": "TICKER1.PA", "conviction": 8, "reason": "Analyse..."}}
  ]
}}

Exemple si le marché est trop dangereux :
{{
  "market_regime": "risk_off",
  "picks": []
}}
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.1-pro-preview',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        data = json.loads(response.text)
        picks = data.get("picks", [])
        market_regime = data.get("market_regime", "inconnu")
    except Exception as e:
        print(f"Erreur lors de l'appel à Gemini : {e}")
        return

    print(f"Diagnostic de l'IA : marché {market_regime}")

    # On limite à 2 maximum au cas où l'IA en renvoie plus
    picks = picks[:2]

    # Discipline de conviction : le prompt interdit tout achat sous 7/10.
    filtered = []
    for pick in picks:
        conv = pick.get('conviction') if isinstance(pick, dict) else None
        if isinstance(conv, (int, float)) and conv < 7:
            print(f"⚠️ {pick.get('company', '?')} écarté : conviction {conv}/10 < 7.")
            continue
        filtered.append(pick)
    picks = filtered

    if len(picks) == 0:
        print("Analyse de l'IA : Marché trop incertain. Aucun achat ne sera effectué aujourd'hui.")
        return
        
    portfolio = []
    paris_tz = pytz.timezone('Europe/Paris')
    today_str = datetime.datetime.now(paris_tz).strftime('%Y-%m-%d')
    
    print("--- ACHAT VIRTUEL ---")
    for pick in picks:
        if not isinstance(pick, dict):
            continue
            
        ticker_symbol = pick.get('ticker')
        company_name = pick.get('company', 'Inconnu')
        reason_text = pick.get('reason', 'Aucune raison spécifiée')
        conviction = pick.get('conviction')
        
        if not ticker_symbol:
            print("❌ L'IA a renvoyé un choix invalide (ticker manquant).")
            continue
            
        try:
            ticker = yf.Ticker(ticker_symbol)
            # Récupère le dernier prix en direct (1 jour, intervalle 1 minute)
            hist = ticker.history(period="1d", interval="1m")
            if not hist.empty:
                current_price = float(hist['Close'].iloc[-1])
                portfolio.append({
                    "company": company_name,
                    "ticker": ticker_symbol,
                    "reason": reason_text,
                    "conviction": conviction,
                    "market_regime": market_regime,
                    "buy_price": current_price,
                    "buy_date": today_str,
                    "amount_eur": 500
                })
                conv_txt = f" (conviction {conviction}/10)" if conviction else ""
                print(f"✅ Achat de 500€ de {company_name} ({ticker_symbol}) à {round(current_price, 2)}€{conv_txt}")
                print(f"   Raison : {reason_text}")
            else:
                print(f"❌ Impossible de récupérer le prix pour {ticker_symbol}")
        except Exception as e:
            print(f"❌ Erreur avec yfinance pour {ticker_symbol} : {e}")
            
    if portfolio:
        save_json(PORTFOLIO_FILE, portfolio)
        print("Nouveau portefeuille enregistré.")

if __name__ == "__main__":
    # Garde-fou : le bot est conçu pour tourner en fin de séance (~17h00 Paris).
    # Toute exécution trop tôt (déclenchement manuel matinal, rattrapage d'une
    # tâche planifiée...) corrompt les données : évaluation sans cotations du
    # jour (performances perdues) et achat à un prix figé de la veille.
    # Constaté les 07/07 (run à 07h10 Paris) et 08/07/2026 (run à 16h18 Paris).
    paris_now = datetime.datetime.now(pytz.timezone('Europe/Paris'))
    if os.environ.get("FORCE_RUN") != "1":
        if paris_now.weekday() >= 5:
            print(f"⛔ Week-end ({paris_now.strftime('%A %d/%m')}) : bourse fermée, exécution annulée.")
            raise SystemExit(0)
        if (paris_now.hour, paris_now.minute) < (16, 45):
            print(f"⛔ Il est {paris_now.strftime('%H:%M')} à Paris : le bot ne doit tourner qu'après 16h45.")
            print("   Exécution annulée pour ne pas corrompre les données (FORCE_RUN=1 pour outrepasser).")
            raise SystemExit(0)

    print(f"--- DÉMARRAGE DU BOT DE TRADING ({datetime.datetime.now(pytz.timezone('Europe/Paris')).strftime('%H:%M:%S')}) ---")
    evaluate_portfolio()
    print("-----------------------------------")
    analyze_and_buy()
    
    print("Génération des rapports...")
    report.generate_charts()
    report.generate_markdown_report()
    
    print("--- FIN DE L'EXÉCUTION ---")

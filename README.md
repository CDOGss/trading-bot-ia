# 📈 Trading Bot IA - Analyste Institutionnel (CAC 40 / SBF 120)

Ce projet est un bot de "paper trading" (simulation boursière automatisée) propulsé par l'intelligence artificielle **Gemini 3.1 Pro (via l'API Google GenAI)**. Il est conçu pour agir comme un gérant de portefeuille institutionnel senior.

Le bot fonctionne de manière 100% autonome grâce à **GitHub Actions**.

## 🧠 Stratégie d'Investissement

Chaque jour de semaine à **17h00 (heure de Paris)**, le bot s'active :
1. **Évaluation** : Il calcule et enregistre les performances des actions achetées la veille (à l'ouverture, à 9h30, à la mi-journée et à la clôture).
2. **Analyse du Marché** : Il lit les flux RSS financiers les plus récents :
   - Actualité Boursière Française (Les Echos, Boursorama)
   - Tendance de Wall Street
   - Contexte Macroéconomique (Banques centrales, taux, inflation)
3. **Prise de décision** : L'IA analyse le sentiment du marché (Risk-on / Risk-off) et l'influence de Wall Street pour choisir **jusqu'à 2 actions** du marché français (CAC 40 / SBF 120) qui ont de fortes chances d'ouvrir en "gap haussier" le lendemain.
4. **Préservation du capital** : Si les voyants sont au rouge ou le marché trop incertain, le bot choisit sciemment de rester liquide (0 achat).

## 🚀 Fonctionnement Automatique

L'automatisation est gérée par le fichier `.github/workflows/trading_bot.yml`.
Il exécute le script `main.py`, qui récupère les cours en temps réel via `yfinance`, et sauvegarde l'état dans deux fichiers :
- `portfolio.json` : Contient les positions actuellement ouvertes.
- `history.json` : Contient l'historique de toutes les positions clôturées avec leurs performances (gains/pertes).

À la fin de chaque exécution, le bot effectue automatiquement un `git commit` et un `git push` pour mettre à jour ces fichiers directement sur ce dépôt GitHub.

## 🛠️ Installation et Exécution Locale

Si vous souhaitez faire tourner le bot manuellement sur votre machine :

1. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
2. Configurez votre clé d'API Gemini en variable d'environnement :
   ```bash
   # Sur Windows (PowerShell)
   $env:GEMINI_API_KEY="votre_cle_api"
   # Sur Linux / Mac
   export GEMINI_API_KEY="votre_cle_api"
   ```
3. Lancez le script :
   ```bash
   python main.py
   ```

## 🔐 Sécurité

La clé d'API de Gemini est stockée de manière totalement sécurisée dans les **Secrets GitHub** (`GEMINI_API_KEY`) et n'apparaît jamais dans le code.

# Nexus Insight Media — Referral Bot

This is a Python-based Reddit bot that scans specified subreddits for high-intent keywords and replies with helpful advice and links to our portfolio site.

## Features
- **Categorized Matching**: Different responses for Laptops, Monitors, chairs, SaaS, and VPNs.
- **Anti-Detection**:
  - Daily limit (max 15 replies/day).
  - Randomized opening phrases.
  - 24-hour post age limit.
  - Organic delays (60-180 seconds) between replies.
  - Persistent state using SQLite (`bot_state.db`) to avoid double-posting.

## Setup
1. **Virtual Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Update `config.json` with real Reddit API credentials and the bot's username/password.

3. **Running**:
   ```bash
   python3 bot.py
   ```

## Files
- `bot.py`: Main bot logic.
- `config.json`: Bot configuration (subreddits, keywords, templates).
- `requirements.txt`: Python dependencies.
- `bot_state.db`: SQLite database for tracking processed posts and daily stats.
- `replies_log.txt`: Log of all simulated replies (useful for debugging before going live).

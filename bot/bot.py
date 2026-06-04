import praw
import json
import time
import os
import sqlite3
import random
from datetime import datetime, timedelta

# Load configuration
def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

# Initialize Reddit client
def get_reddit(config):
    creds = config['reddit']
    if creds['client_id'] == "YOUR_CLIENT_ID":
        print("WARNING: Using default credentials. Reddit API calls will fail.")
        return None
    return praw.Reddit(
        client_id=creds['client_id'],
        client_secret=creds['client_secret'],
        user_agent=creds['user_agent'],
        username=creds['username'],
        password=creds['password']
    )

# Initialize SQLite DB for processed IDs and rate limiting
def init_db(db_path='bot_state.db'):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS processed_ids 
                 (id TEXT PRIMARY KEY, type TEXT, category TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS reply_stats 
                 (date TEXT PRIMARY KEY, count INTEGER)''')
    conn.commit()
    return conn

# Check if post was already processed
def is_processed(conn, post_id):
    c = conn.cursor()
    c.execute('SELECT 1 FROM processed_ids WHERE id = ?', (post_id,))
    return c.fetchone() is not None

# Save processed ID
def save_processed_id(conn, post_id, post_type, category):
    c = conn.cursor()
    c.execute('INSERT INTO processed_ids (id, type, category, timestamp) VALUES (?, ?, ?, ?)', 
              (post_id, post_type, category, datetime.now()))
    conn.commit()

# Check daily limit
def check_daily_limit(conn, limit=15):
    today = datetime.now().strftime('%Y-%m-%d')
    c = conn.cursor()
    c.execute('SELECT count FROM reply_stats WHERE date = ?', (today,))
    row = c.fetchone()
    if row and row[0] >= limit:
        return False
    return True

# Increment daily count
def increment_daily_count(conn):
    today = datetime.now().strftime('%Y-%m-%d')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO reply_stats (date, count) VALUES (?, COALESCE((SELECT count FROM reply_stats WHERE date = ?), 0) + 1)', 
              (today, today))
    conn.commit()

def reply(item, template, item_type, category, config):
    try:
        settings = config['bot']['settings']
        # Randomized opening variations based on Alex persona
        openings = [
            "Great question! ", 
            "I was looking into this recently too. ",
            "Hey! Just saw your post. ",
            "Interesting question. ",
            "I've spent a lot of time comparing products in this category. ",
            "I actually had to make this same decision a few months back. "
        ]
        
        # Add persona flavor if configured
        persona = config['bot'].get('persona', {})
        prefix = ""
        if persona.get('name') == "Alex":
            prefix = random.choice(openings)

        final_text = prefix + template
        
        is_simulation = settings.get('simulation_mode', True)
        
        if is_simulation:
            with open('replies_log.txt', 'a') as f:
                f.write(f"--- SIMULATION {datetime.now()} ---\n")
                f.write(f"Category: {category} | Type: {item_type} | ID: {item.id}\n")
                f.write(f"Author: {getattr(item, 'author', 'unknown')}\n")
                f.write(f"Subreddit: {item.subreddit.display_name}\n")
                f.write(f"Reply: {final_text}\n\n")
            print(f"[SIMULATION] Would have replied to {category} {item_type} {item.id}")
        else:
            item.reply(final_text)
            print(f"REAL REPLY sent to {category} {item_type} {item.id}")
        
        return True
    except Exception as e:
        print(f"Failed to reply to {item.id}: {e}")
        return False

# Main bot loop
def run_bot():
    config = load_config()
    reddit = get_reddit(config)
    conn = init_db()
    
    if not reddit:
        print("Bot cannot start without valid Reddit credentials.")
        return

    subreddits_to_scan = config['bot']['subreddits']
    categories = config['bot']['categories']
    
    print(f"Bot started at {datetime.now()} (Simulation: {config['bot']['settings'].get('simulation_mode', True)})")
    
    while True:
        try:
            settings = config['bot']['settings']
            if not check_daily_limit(conn, limit=settings.get('daily_comment_limit', 15)):
                print("Daily limit reached. Sleeping until tomorrow.")
                time.sleep(3600) # Check again in an hour
                continue

            for subreddit_name in subreddits_to_scan:
                subreddit = reddit.subreddit(subreddit_name)
                print(f"Scanning r/{subreddit_name}...")
                
                # Scan new submissions (last X hours)
                max_age_hours = settings.get('max_post_age_hours', 24)
                for submission in subreddit.new(limit=10):
                    if is_processed(conn, submission.id):
                        continue
                        
                    # Check age
                    created_time = datetime.fromtimestamp(submission.created_utc)
                    if datetime.now() - created_time > timedelta(hours=max_age_hours):
                        continue

                    for cat_name, cat_data in categories.items():
                        if any(kw.lower() in submission.title.lower() or kw.lower() in submission.selftext.lower() for kw in cat_data['keywords']):
                            print(f"Match found in submission ({cat_name}): {submission.title}")
                            if reply(submission, cat_data['template'], 'submission', cat_name, config):
                                save_processed_id(conn, submission.id, 'submission', cat_name)
                                increment_daily_count(conn)
                                # Organic delay between replies
                                delay = random.randint(
                                    settings.get('min_delay_minutes', 12) * 60, 
                                    settings.get('max_delay_minutes', 45) * 60
                                )
                                print(f"Sleeping for {delay} seconds...")
                                time.sleep(delay)
                            break
                
                # Scan comments
                for comment in subreddit.comments(limit=20):
                    if is_processed(conn, comment.id):
                        continue
                    
                    if comment.author and comment.author.name == config['reddit']['username']:
                        continue

                    # Check age for comments too
                    created_time = datetime.fromtimestamp(comment.created_utc)
                    if datetime.now() - created_time > timedelta(hours=max_age_hours):
                        continue

                    for cat_name, cat_data in categories.items():
                        if any(kw.lower() in comment.body.lower() for kw in cat_data['keywords']):
                            print(f"Match found in comment ({cat_name}) by {comment.author}")
                            if reply(comment, cat_data['template'], 'comment', cat_name, config):
                                save_processed_id(conn, comment.id, 'comment', cat_name)
                                increment_daily_count(conn)
                                delay = random.randint(
                                    settings.get('min_delay_minutes', 12) * 60, 
                                    settings.get('max_delay_minutes', 45) * 60
                                )
                                print(f"Sleeping for {delay} seconds...")
                                time.sleep(delay)
                            break
            
            # Global loop delay
            print("Loop complete. Sleeping for 10 minutes...")
            time.sleep(600)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()

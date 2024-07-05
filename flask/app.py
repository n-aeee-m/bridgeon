from flask import Flask, render_template
import feedparser
import sched
import time
from bs4 import BeautifulSoup
import sqlite3
import threading

app = Flask(__name__)

# Initialize SQLite database
def create_db():
    conn = sqlite3.connect('feed_entries.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS feed_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            link TEXT,
            description TEXT,
            image TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Function to fetch and parse RSS feeds
def fetch_rss_feed(url):
    return feedparser.parse(url)

# Function to extract image URL from the feed entry
def extract_image(entry):
    if 'media_content' in entry:
        return entry.media_content[0]['url']
    elif 'media_thumbnail' in entry:
        return entry.media_thumbnail[0]['url']
    
    description = entry.get('description', '')
    img_tag = BeautifulSoup(description, 'html.parser').find('img')
    if img_tag:
        return img_tag['src']
    
    return None

# Function to update feed data
def update_feed_data(scheduler):
    all_feed_data = []
    rss_feed_urls = [
        'http://rss.cnn.com/rss/edition.rss',  # Example RSS feed 1
        'http://feeds.bbci.co.uk/news/rss.xml',
        'https://www.onmanorama.com/news/india.feeds.onmrss.xml',
        'https://www.cbsnews.com/latest/rss/us',
        'https://rss.nytimes.com/services/xml/rss/nyt/us.xml',
        'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',
        'http://rss.cnn.com/rss/cnn_latest.rss/'
        # Add more RSS feed URLs as needed
    ]
    
    print("Fetching new feeds...")
    for url in rss_feed_urls:
        try:
            print(f"Fetching from: {url}")
            feed = fetch_rss_feed(url)
            if feed.entries:
                entry_count = 0
                for entry in feed.entries:
                    entry_count += 1
                    image_url = extract_image(entry)
                    feed_item = {
                        'title': entry.get('title', 'No title available'),
                        'link': entry.get('link', '#'),
                        'description': entry.get('description', 'No description available'),
                        'image': image_url
                    }
                    all_feed_data.append(feed_item)
                    
                    # Check if entry already exists in SQLite
                    if not entry_exists(entry):
                        save_to_db(feed_item)  # Save new entry to SQLite
                
                print(f"Fetched {entry_count} entries from: {url}")
    
        except Exception as e:
            print(f"Error fetching from {url}: {e}")
    
    # Update the global variable with the latest feed data
    global feed_data
    feed_data = all_feed_data
    
    # Schedule the next update after 10 seconds
    scheduler.enter(10, 1, update_feed_data, (scheduler,))

# Function to check if entry already exists in SQLite
def entry_exists(entry):
    conn = sqlite3.connect('feed_entries.db')
    c = conn.cursor()
    c.execute('''
        SELECT * FROM feed_entries
        WHERE title = ? AND link = ?
    ''', (entry.get('title', ''), entry.get('link', '')))
    result = c.fetchone()
    conn.close()
    return result is not None

# Function to save feed item to SQLite
def save_to_db(feed_item):
    conn = sqlite3.connect('feed_entries.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO feed_entries (title, link, description, image)
        VALUES (?, ?, ?, ?)
    ''', (feed_item['title'], feed_item['link'], feed_item['description'], feed_item['image']))
    conn.commit()
    conn.close()

# Function to fetch all entries from SQLite
def fetch_entries_from_db():
    conn = sqlite3.connect('feed_entries.db')
    c = conn.cursor()
    c.execute('''
        SELECT * FROM feed_entries
        ORDER BY timestamp DESC
    ''')
    entries = c.fetchall()
    conn.close()
    
    feed_data = []
    for entry in entries:
        feed_item = {
            'title': entry[1],
            'link': entry[2],
            'description': entry[3],
            'image': entry[4]
        }
        feed_data.append(feed_item)
    
    return feed_data

# Initialize SQLite database
create_db()

# Initialize scheduler
scheduler = sched.scheduler(time.time, time.sleep)

# Schedule the first update immediately
scheduler.enter(0, 1, update_feed_data, (scheduler,))

# Start the scheduler thread in a separate daemon thread
scheduler_thread = threading.Thread(target=scheduler.run, kwargs={'blocking': True})
scheduler_thread.daemon = True
scheduler_thread.start()

# Global variable to hold the latest feed data
feed_data = []

# Flask route to render home page
@app.route('/')
def home():
    global feed_data
    feed_data = fetch_entries_from_db()
    return render_template('index.html', feed_data=feed_data)

if __name__ == '__main__':
    app.run(debug=True)

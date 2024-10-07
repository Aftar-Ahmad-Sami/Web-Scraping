import sqlite3
import json

def export_to_json(db_file='scraped_urls.db', json_file='exported_urls.json'):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    cursor.execute("SELECT url, scraped_at FROM urls")
    rows = cursor.fetchall()
    
    # Convert to list of dictionaries
    data = [{'url': row[0], 'scraped_at': row[1]} for row in rows]
    
    # Write to JSON file
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    
    print(f"Data exported to {json_file}")
    conn.close()

if __name__ == "__main__":
    export_to_json()

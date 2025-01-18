import sqlite3

def clean_price_field():
    conn = sqlite3.connect('cars.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, price FROM price_history")
    records = cursor.fetchall()
    
    print(f"Found {len(records)} records to process")
    
    # Update each record
    cleaned_count = 0
    for record_id, price in records:
        # Clean both regular spaces and non-breaking spaces (\xa0)
        clean_price = price.replace('\xa0', '').replace(' ', '')
        if clean_price != price:
            cursor.execute("UPDATE price_history SET price = ? WHERE id = ?", (clean_price, record_id))
            print(f"Cleaned price_history for id {record_id}: {price} -> {clean_price}")
            cleaned_count += 1
    
    conn.commit()
    conn.close()
    print(f"Database cleaning completed. Cleaned {cleaned_count} records")

if __name__ == "__main__":
    clean_price_field()

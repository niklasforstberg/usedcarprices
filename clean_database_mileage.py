import sqlite3

def inspect_mileage():
    conn = sqlite3.connect('cars.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, mileage FROM cars")
    records = cursor.fetchall()
    
    print(f"Total records: {len(records)}")
    print("\nFirst 10 records with detailed info:")
    print("-" * 50)
    
    for record_id, mileage in records[:10]:
        print(f"\nID: {record_id}")
        print(f"Mileage type: {type(mileage)}")
        print(f"Mileage repr: {repr(mileage)}")
        print(f"Mileage str: {str(mileage)}")
    
    print("\nAll records:")
    print("-" * 50)
    #for record_id, mileage in records:
        #print(f"{record_id} | '{mileage}'")
    conn.close()

def clean_mileage_field():
    conn = sqlite3.connect('cars.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, mileage FROM cars")
    records = cursor.fetchall()
    
    print(f"Found {len(records)} records to process")
    
    # Update each record
    cleaned_count = 0
    for record_id, mileage in records:
        # Clean spaces, non-breaking spaces, and remove 'mil'
        clean_mileage = mileage.replace('\xa0', '').replace(' ', '').replace('mil', '')
        if clean_mileage != mileage:
            cursor.execute("UPDATE cars SET mileage = ? WHERE id = ?", (clean_mileage, record_id))
            print(f"Cleaned mileage for id {record_id}: {mileage} -> {clean_mileage}")
            cleaned_count += 1
    
    conn.commit()
    conn.close()
    print(f"Database cleaning completed. Cleaned {cleaned_count} records")

if __name__ == "__main__":

    #inspect_mileage()
    clean_mileage_field()
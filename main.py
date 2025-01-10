import requests
from bs4 import BeautifulSoup
import re
import time
from fake_useragent import UserAgent
import sqlite3
from datetime import datetime

def clean_text(text):
    # Remove HTML entities and extra whitespace
    return re.sub(r'&#xA0;', '', text).strip()

def fetch_cars(url, params, headers):

    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return None
    # Save response to file with make, model and timestamp for debugging
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    make = params.get('Makes', 'unknown')
    models = '-'.join(params.get('Models', ['unknown'])) if isinstance(params.get('Models'), list) else params.get('Models', 'unknown')
    filename = f'response_{make}_{models}_{timestamp}.html'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(response.text)
    return response.text

def setup_database():
    conn = sqlite3.connect('cars.db')
    c = conn.cursor()
    
    # Create cars table
    c.execute('''
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            make TEXT,
            model TEXT,
            year INTEGER,
            mileage TEXT,
            price TEXT,
            url TEXT,
            first_seen DATETIME,
            last_seen DATETIME
        )
    ''')
    
    # Create scraping_logs table for tracking runs
    c.execute('''
        CREATE TABLE IF NOT EXISTS scraping_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            cars_found INTEGER,
            search_params TEXT
        )
    ''')
    
    conn.commit()
    return conn

def store_car(conn, car_data):
    c = conn.cursor()
    
    # Check if car already exists (using URL as unique identifier)
    c.execute('SELECT id, first_seen FROM cars WHERE url = ?', (car_data['url'],))
    result = c.fetchone()
    
    if result:
        # Update existing car
        car_id, first_seen = result
        c.execute('''
            UPDATE cars 
            SET title=?, make=?, model=?, year=?, mileage=?, price=?, last_seen=?
            WHERE id=?
        ''', (
            car_data['title'], 
            car_data['make'],
            car_data['model'],
            car_data['year'],
            car_data['mileage'],
            car_data['price'],
            datetime.now(),
            car_id
        ))
    else:
        # Insert new car
        now = datetime.now()
        c.execute('''
            INSERT INTO cars (title, make, model, year, mileage, price, url, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            car_data['title'],
            car_data['make'],
            car_data['model'],
            car_data['year'],
            car_data['mileage'],
            car_data['price'],
            car_data['url'],
            now,
            now
        ))
    
    conn.commit()

def parse_cars(html_content, conn):
    soup = BeautifulSoup(html_content, 'html.parser')
    car_list = soup.find('ul', {'class': 'result-list'})
    if not car_list:
        print("No car list found")
        return 0
        
    car_items = car_list.find_all('li', {'class': 'result-list-item'})
    if not car_items:
        print("No cars found")
        return 0
    
    cars_found = 0
    for car in car_items:
        # Get title and URL
        title_elem = car.find('h3', {'class': 'car-list-header'})
        if not title_elem or not title_elem.find('a'):
            continue
        title = title_elem.find('a').text.strip()
        url = title_elem.find('a')['href']
        
        # Try to extract make and model from title
        title_parts = title.split(' ', 2)
        make = title_parts[0] if len(title_parts) > 0 else 'Unknown'
        model = title_parts[1] if len(title_parts) > 1 else 'Unknown'
        
        # Get year, mileage and location
        details = car.find('p', {'class': 'uk-text-truncate'})
        if not details:
            continue
            
        details_text = [d.strip() for d in details.text.split('|')]
        year = clean_text(details_text[0])
        mileage = clean_text(details_text[1]) if len(details_text) > 1 else 'N/A'
        
        # Get price
        price_elem = car.find('span', {'class': 'car-price-main'})
        price = clean_text(price_elem.text) if price_elem else 'N/A'
        
        # Store in database
        car_data = {
            'title': title,
            'make': make,
            'model': model,
            'year': year,
            'mileage': mileage,
            'price': price,
            'url': url
        }
        store_car(conn, car_data)
        
        # Print to console
        print(f"Title: {title}")
        print(f"Make: {make}")
        print(f"Model: {model}")
        print(f"Year: {year}")
        print(f"Mileage: {mileage}")
        print(f"Price: {price}")
        print(f"URL: {url}")
        print("-" * 50)
        
        cars_found += 1
    
    return cars_found

def log_scraping_run(conn, cars_found, search_params):
    c = conn.cursor()
    c.execute('''
        INSERT INTO scraping_logs (timestamp, cars_found, search_params)
        VALUES (?, ?, ?)
    ''', (datetime.now(), cars_found, str(search_params)))
    conn.commit()

def main():
    conn = setup_database()
    
    url = 'https://www.bytbil.com/bil'
    params = {
        'VehicleType': 'bil',
        'Makes': 'Volvo',
        'Models': ['142', '144', '145'],
        'FreeText': '',
        'SortParams.SortField': 'publishedDate',
        'SortParams.IsAscending': 'False'
    }

    html_content = fetch_cars(url, params)
    if html_content:
        cars_found = parse_cars(html_content, conn)
        log_scraping_run(conn, cars_found, params)
    
    conn.close()

if __name__ == "__main__":
    main()
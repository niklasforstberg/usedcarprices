import requests
from bs4 import BeautifulSoup
import re
import time
import random
import asyncio
import aiohttp
from fake_useragent import UserAgent
import sqlite3
from datetime import datetime
from urllib.parse import urljoin

async def human_like_delay():
    if random.random() < 0.1:
        delay = random.uniform(8, 15)  # Occasionally take longer breaks
    else:
        delay = random.uniform(2, 7)   # Normal browsing delays
    delay += random.random() * 0.5     # Add some noise
    print(f"Sleeping for {delay} seconds")
    await asyncio.sleep(delay)

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
            location TEXT,
            price TEXT,
            registration_number TEXT,
            color TEXT,
            drive_type TEXT,
            gearbox TEXT,
            bodytype TEXT,
            first_seen DATETIME,
            last_seen DATETIME,
            url TEXT
        )
    ''')
    
    # Create scraping_logs table
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

async def fetch_car_details(session, url, headers):
    await human_like_delay()
    
    try:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                print(f"Error fetching car details: {response.status}")
                return None
            
            html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            details = {}
            
            # Find registration number
            reg_elem = soup.find('dt', string='Regnr')
            if reg_elem and reg_elem.find_next_sibling('dd'):
                details['registration_number'] = reg_elem.find_next_sibling('dd').text.strip()
            
            # Find color
            color_elem = soup.find('dt', string='Färg')
            if color_elem and color_elem.find_next_sibling('dd'):
                details['color'] = color_elem.find_next_sibling('dd').text.strip()
            
            # Find drive type
            drive_elem = soup.find('dt', string='Drivhjul')
            if drive_elem and drive_elem.find_next_sibling('dd'):
                details['drive_type'] = drive_elem.find_next_sibling('dd').text.strip()
            
            # Find gearbox
            gearbox_elem = soup.find('dt', string='Växellåda')
            if gearbox_elem and gearbox_elem.find_next_sibling('dd'):
                details['gearbox'] = gearbox_elem.find_next_sibling('dd').text.strip()
            
            # Find bodytype
            bodytype_elem = soup.find('dt', string='Karosseri')
            if bodytype_elem and bodytype_elem.find_next_sibling('dd'):
                details['bodytype'] = bodytype_elem.find_next_sibling('dd').text.strip()
            
            return details
            
    except Exception as e:
        print(f"Error fetching car details: {e}")
        return None

def store_car(conn, car_data):
    c = conn.cursor()
    
    # Check if car already exists
    c.execute('SELECT id, first_seen FROM cars WHERE registration_number = ? OR url = ?', 
             (car_data.get('registration_number'), car_data['url']))
    result = c.fetchone()
    
    if result:
        # Update existing car
        print(f"Updating existing car: {car_data['title']} (First seen: {first_seen})")
        car_id, first_seen = result
        c.execute('''
            UPDATE cars 
            SET title=?, make=?, model=?, year=?, mileage=?, location=?, price=?, 
                registration_number=?, color=?, drive_type=?, gearbox=?, bodytype=?, last_seen=?
            WHERE id=?
        ''', (
            car_data['title'], 
            car_data['make'],
            car_data['model'],
            car_data['year'],
            car_data['mileage'],
            car_data['location'],
            car_data['price'],
            car_data.get('registration_number'),
            car_data.get('color'),
            car_data.get('drive_type'),
            car_data.get('gearbox'),
            car_data.get('bodytype'),
            datetime.now(),
            car_id
        ))
    else:
        # Insert new car
        now = datetime.now()
        c.execute('''
            INSERT INTO cars (
                title, make, model, year, mileage, location, price, url, 
                registration_number, color, drive_type, gearbox, bodytype,
                first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            car_data['title'],
            car_data['make'],
            car_data['model'],
            car_data['year'],
            car_data['mileage'],
            car_data['location'],
            car_data['price'],
            car_data['url'],
            car_data.get('registration_number'),
            car_data.get('color'),
            car_data.get('drive_type'),
            car_data.get('gearbox'),
            car_data.get('bodytype'),
            now,
            now
        ))
    
    conn.commit()

async def parse_cars(html_content, conn, session, headers):
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
    new_cars = 0
    updated_cars = 0
    
    for car in car_items:
        # Get title and URL
        title_elem = car.find('h3', {'class': 'car-list-header'})
        if not title_elem or not title_elem.find('a'):
            continue
            
        title = title_elem.find('a').text.strip()
        relative_url = title_elem.find('a')['href']
        url = urljoin('https://www.bytbil.com', relative_url)
        
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
        location = clean_text(details_text[2]) if len(details_text) > 2 else 'N/A'
        
        # Get price
        price_elem = car.find('span', {'class': 'car-price-main'})
        price = clean_text(price_elem.text).replace('kr', '').replace(' ', '') if price_elem else 'N/A'
        
        # Store in database
        car_data = {
            'title': title,
            'make': make,
            'model': model,
            'year': year,
            'mileage': mileage,
            'location': location,
            'price': price,
            'url': url
        }
        
        # Fetch additional details
        car_details = await fetch_car_details(session, url, headers)
        if car_details:
            car_data.update(car_details)
        
        # Check if car exists before storing
        c = conn.cursor()
        c.execute('SELECT id FROM cars WHERE registration_number = ? OR url = ?', 
                 (car_data.get('registration_number'), car_data['url']))
        exists = c.fetchone()
        
        store_car(conn, car_data)
        cars_found += 1
        
        if exists:
            updated_cars += 1
        else:
            new_cars += 1
        
        print(f"Processed: {title} ({car_data.get('registration_number', 'N/A')}) - Price: {price}")
    
    print(f"\nSummary:")
    print(f"Total cars processed: {cars_found}")
    print(f"New cars added: {new_cars}")
    print(f"Existing cars updated: {updated_cars}")
    
    return cars_found

def log_scraping_run(conn, cars_found, search_params):
    c = conn.cursor()
    c.execute('''
        INSERT INTO scraping_logs (timestamp, cars_found, search_params)
        VALUES (?, ?, ?)
    ''', (datetime.now(), cars_found, str(search_params)))
    conn.commit()

async def main():
    conn = setup_database()
    base_url = 'https://www.bytbil.com/bil'
    
    # Initial params remain the same
    params = {
        'VehicleType': 'bil',
        'Makes': 'Tesla',
        'Models': ['Model Y'],
        'FreeText': '',
        'Regions': '',  # URL encoding handled automatically
        'PriceRange.From': '',
        'PriceRange.To': '',
        'ModelYearRange.From': '',
        'ModelYearRange.To': '',
        'MilageRange.From': '',
        'MilageRange.To': '',
        'BodyTypes': '',  # Can be: Cab, Halvkombi, Kombi, Minibuss, SUV, Sedan, Sportkupé
        'Fuels': '',  # Can be: Bensin, Diesel, El, Elhybrid, etc.
        'Gearboxes': '',  # Can be: Manuell, Automatisk
        'EnginePowerRange.From': '',
        'EnginePowerRange.To': '',
        'ShowLeasingOffers': 'False',
        'ShowImportedOffers': '',
        'ElectricRangeRange.From': '',
        'ElectricRangeRange.To': '',
        'SortParams.SortField': 'publishedDate',
        'SortParams.IsAscending': 'False'
    }
    
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.bytbil.com/'
    }

    async with aiohttp.ClientSession() as session:
        page = 1
        total_cars = 0
        
        while True:
            # Add page parameter for pagination
            params['Page'] = page
            params['IgnoreSortFiltering'] = False
            
            response = await session.get(base_url, params=params, headers=headers)
            if response.status == 200:
                html_content = await response.text()
                
                # Parse cars on current page
                cars_found = await parse_cars(html_content, conn, session, headers)
                total_cars += cars_found
                
                # Check if we should continue to next page
                if cars_found == 0:  # No more cars found on this page
                    break
                    
                print(f"Processed page {page}, found {cars_found} cars")
                page += 1
                
                # Add human-like delay between pages
                await human_like_delay()
            else:
                print(f"Error fetching page {page}: {response.status}")
                break
    
        print(f"Total cars processed: {total_cars}")
        log_scraping_run(conn, total_cars, params)
    
    conn.close()

if __name__ == "__main__":
    asyncio.run(main()) 
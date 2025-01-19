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
import argparse
import signal

# This program fetches data from bytbil.com and stores the information in a sqlite db.
# Written by Niklas Förstberg, 2025 
#
# Todo: Check memory useage och se om man kan optimera det.
# Todo: Add functionality to scrape for several different makes in the same run

# Use this query to find price history for a car
# SELECT ph.price, ph.timestamp 
# FROM price_history ph 
# JOIN cars c ON ph.car_id = c.id 
# WHERE c.registration_number = ?
# ORDER BY ph.timestamp DESC

async def human_like_delay():
    if random.random() < 0.1:
        delay = random.uniform(5, 9)  # Occasionally take longer breaks
    else:
        delay = random.uniform(2, 5)   # Normal browsing delays
    delay += random.random() * 0.5     # Add some noise
    print(f"Sleeping for {delay} seconds")
    await asyncio.sleep(delay)

def clean_text(text):
    # Remove HTML entities and all whitespace including non-breaking spaces
    return re.sub(r'(?:&#xA0;|\xa0|\s+)', '', text).strip()

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
            url TEXT,
            scraping_run_id INTEGER REFERENCES scraping_logs(id)
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
    
    # Create price_history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            car_id INTEGER,
            price TEXT,
            timestamp DATETIME,
            FOREIGN KEY (car_id) REFERENCES cars(id)
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
            
            more_car_data = {}
            
            # Find registration number
            reg_elem = soup.find('dt', string='Regnr')
            if reg_elem and reg_elem.find_next_sibling('dd'):
                more_car_data['registration_number'] = reg_elem.find_next_sibling('dd').text.strip()
            
            # Find color
            color_elem = soup.find('dt', string='Färg')
            if color_elem and color_elem.find_next_sibling('dd'):
                more_car_data['color'] = color_elem.find_next_sibling('dd').text.strip()
            
            # Find drive type
            drive_elem = soup.find('dt', string='Drivhjul')
            if drive_elem and drive_elem.find_next_sibling('dd'):
                more_car_data['drive_type'] = drive_elem.find_next_sibling('dd').text.strip()
            
            # Find gearbox
            gearbox_elem = soup.find('dt', string='Växellåda')
            if gearbox_elem and gearbox_elem.find_next_sibling('dd'):
                more_car_data['gearbox'] = gearbox_elem.find_next_sibling('dd').text.strip()
            
            # Find bodytype
            bodytype_elem = soup.find('dt', string='Karosseri')
            if bodytype_elem and bodytype_elem.find_next_sibling('dd'):
                more_car_data['bodytype'] = bodytype_elem.find_next_sibling('dd').text.strip()
            
            return more_car_data
            
    except Exception as e:
        print(f"Error fetching car details: {e}")
        return None

def store_car(conn, car_data, c, scraping_run_id):

    # Check if car already exists, first by car registration number
    # We already checked this in parse_cars, but a car might have been relisted with a new URL
    if (car_data.get('registration_number') is not None and 
        car_data.get('registration_number') != 'N/A' and 
        car_data.get('registration_number') != '-'):
        
        c.execute('SELECT id, price FROM cars WHERE registration_number = ?', 
                 (car_data['registration_number'],))
        result = c.fetchone()
    else:
        #check by url if no car reg
        c.execute('SELECT id, price FROM cars WHERE url = ?', 
                 (car_data['url'],))
        result = c.fetchone()
    
    if result:
        #Car found, update it
        car_id, current_price = result
        new_price = car_data['price']
        
        # Only store price history if price has changed
        if current_price != new_price:
            c.execute('''
                INSERT INTO price_history (car_id, price, timestamp)
                VALUES (?, ?, ?)
            ''', (car_id, current_price, datetime.now()))
            print(f" -- Price change detected for car {car_data.get('registration_number')}: {current_price} -> {new_price}")
        
        # Update only the fields we have
        update_fields = {
            'title': car_data['title'],
            'make': car_data['make'],
            'model': car_data['model'],
            'year': car_data['year'],
            'mileage': car_data['mileage'],
            'location': car_data['location'],
            'price': car_data['price'],
            'last_seen': datetime.now(),
            'scraping_run_id': scraping_run_id
        }
        
        # Build dynamic update query
        fields = ', '.join(f"{key}=?" for key in update_fields.keys())
        query = f'UPDATE cars SET {fields} WHERE id=?'
        
        # Execute update with values
        values = list(update_fields.values()) + [car_id]
        c.execute(query, values)
    else:
        # Insert new car
        now = datetime.now()
        c.execute('''
            INSERT INTO cars (
                title, make, model, year, mileage, location, price, url, 
                registration_number, color, drive_type, gearbox, bodytype,
                first_seen, last_seen, scraping_run_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            now,
            scraping_run_id
        ))
    
    conn.commit()

async def parse_cars(html_content, conn, session, headers, counters, make, model, stop_flag, scraping_run_id):
    if stop_flag.is_set():
        return 0
    
    soup = BeautifulSoup(html_content, 'html.parser')
    car_list = soup.find('ul', {'class': 'result-list'})
    if not car_list:
        print("No more cars found")
        return 0
        
    car_items = car_list.find_all('li', {'class': 'result-list-item'})
    if not car_items:
        print("No cars found")
        return 0
    
    page_cars = 0
    c = conn.cursor()  # Create cursor once for all checks
    
    for car in car_items:
        if stop_flag.is_set():
            return page_cars
        
        # Get price
        price_elem = car.find('span', {'class': 'car-price-main'})
        if price_elem:
            price_text = clean_text(price_elem.text)
            if any(variant in price_text.lower() for variant in ['/mån', '/månad']):
                continue  # Skip this car, it's a leasing offer
            price = price_text.replace('kr', '').replace(' ', '')
        else:
            continue  # Skip if no price found

        # Get title
        title_elem = car.find('h3', {'class': 'car-list-header'})
        if not title_elem or not title_elem.find('a'):
            continue
        title = title_elem.find('a').text.strip()

        #Get URL
        relative_url = title_elem.find('a')['href']
        url = urljoin('https://www.bytbil.com', relative_url)

        # Check if car exists before fetching details
        c.execute('SELECT id FROM cars WHERE url = ?', (url,))
        exists = c.fetchone()

        # Get year, mileage and location
        details = car.find('p', {'class': 'uk-text-truncate'})
        if not details:
            continue        
        details_text = [d.strip() for d in details.text.split('|')]
        year = clean_text(details_text[0])
        mileage = clean_text(details_text[1]).replace('mil', '') if len(details_text) > 1 else 'N/A'
        location = clean_text(details_text[2]) if len(details_text) > 2 else 'N/A'
        
        # Data to store in database
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
        
        # Only fetch additional details if car doesn't exist
        if not exists:
            more_car_data = await fetch_car_details(session, url, headers)
            if more_car_data:
                car_data.update(more_car_data)
        
        store_car(conn, car_data, c, scraping_run_id)
        counters['total'] += 1
        page_cars += 1
        
        if exists:
            counters['updated'] += 1
        else:
            counters['new'] += 1
        
        reg_num = car_data.get('registration_number', '')
        print(f"#{counters['total']} Processed: {title} {year}  {mileage} mil [{reg_num}] {price}kr")
    
    return page_cars

def log_scraping_run(conn, search_params):
    c = conn.cursor()
    c.execute('''
        INSERT INTO scraping_logs (timestamp, search_params)
        VALUES (?, ?)
    ''', (datetime.now(), str(search_params)))
    scraping_run_id = c.lastrowid
    conn.commit()
    return scraping_run_id
    

def update_scraping_run(conn, scraping_run_id, cars_found):
    c = conn.cursor()
    c.execute('UPDATE scraping_logs SET cars_found = ? WHERE id = ?', (cars_found, scraping_run_id))
    conn.commit()

async def main():
    stop_flag = asyncio.Event()
    
    def signal_handler():
        print("\nStopping gracefully... Please wait for current operations to complete.")
        stop_flag.set()

    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    make = 'Toyota'
    model = 'Avensis'

    start_time = time.time() 

    parser = argparse.ArgumentParser(description='Scrape car listings from bytbil.com')
    parser.add_argument('--make', type=str, default=make, help='Car manufacturer')
    parser.add_argument('--model', type=str, default=model, help='Car model')
    args = parser.parse_args()

    make = args.make
    model = args.model

    conn = setup_database()
    base_url = 'https://www.bytbil.com/bil'
    
    # Initial params
    first_page_params = {
        'VehicleType': 'bil',
        'Makes': make,
        'Models': model,
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
        'ShowLeasingOffers': 'false',
        'ShowImportedOffers': '',
        'ElectricRangeRange.From': '',
        'ElectricRangeRange.To': '',
        'SortParams.SortField': 'publishedDate',
        'SortParams.IsAscending': 'false',
        'IgnoreSortFiltering': 'false'
    }
    
    # Params format for subsequent pages
    paginated_params = {
        'Makes[0]': make,
        'Models[0]': model,
        'OnlyNew': 'False',
        'OnlyWarrantyProgram': 'False',
        'OnlyEnvironmentFriendly': 'False',
        'OnlyFourWheelDrive': 'False',
        'OnlyReducedPrice': 'False',
        'OnlyDeductibleVAT': 'False',
        'OnlyIsAuction': 'False',
        'OnlyAuthorizedDealers': 'False',
        'OnlyHasImage': 'False',
        'OnlyHasVideo': 'False',
        'OnlyHasCarfaxReport': 'False',
        'OnlyNoBonusMalus': 'False',
        'FreeText': '',
        'Page': '1',
        'IgnoreSortFiltering': 'False'
    }
    
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://www.bytbil.com/'
    }

    counters = {
        'total': 0,
        'new': 0,
        'updated': 0
    }

    scraping_run_id = log_scraping_run(conn, first_page_params)
    
    async with aiohttp.ClientSession() as session:
        # First page uses different param format
        response = await session.get(base_url, params=first_page_params, headers=headers)
        if response.status == 200:
            html_content = await response.text()
            cars_found = await parse_cars(html_content, conn, session, headers, counters, make, model, stop_flag, scraping_run_id)
            total_cars = cars_found
            
            # Subsequent pages use paginated format
            page = 2
            while True:
                print(f".Fetching result page {page}")
                paginated_params['Page'] = str(page)
                await human_like_delay()
                response = await session.get(base_url, params=paginated_params, headers=headers)
                if response.status == 200:
                    html_content = await response.text()
                    cars_found = await parse_cars(html_content, conn, session, headers, counters, make, model, stop_flag, scraping_run_id)
                    if cars_found == 0:
                        break
                    total_cars += cars_found
                    print(f"Processed page {page}, found {cars_found} cars")
                    page += 1
                else:
                    print(f"Error fetching page {page}: {response.status}")
                    break
    
    update_scraping_run(conn, scraping_run_id, total_cars)
    
    print(f"\nFinal Summary:")
    print(f"Total cars processed: {counters['total']}")
    print(f"New cars added: {counters['new']}")
    print(f"Existing cars updated: {counters['updated']}")
    execution_time = time.time() - start_time
    hours = execution_time // 3600
    minutes = (execution_time % 3600) // 60
    seconds = execution_time % 60
    print(f"{int(hours)}h {int(minutes)}m {seconds:.2f}s")

    conn.close()

if __name__ == "__main__":
    asyncio.run(main()) 
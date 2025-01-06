import asyncio
import json
import random
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from urllib.parse import urlencode

async def human_like_delay():
    if random.random() < 0.1:
        delay = random.uniform(8, 15)
    else:
        delay = random.uniform(2, 7)
    delay += random.random() * 0.5
    await asyncio.sleep(delay)

async def fetch_cars(make, model, year=None):
    cookies = [
        {
            'name': 'bb.vehicletype',
            'value': 'car',
            'url': 'https://www.bytbil.com'
        },
        {
            'name': 'takeover',
            'value': 'true',
            'url': 'https://www.bytbil.com'
        },
        {
            'name': 'bb.filters_toggled',
            'value': 'true',
            'url': 'https://www.bytbil.com'
        }
    ]
    
    user_agents = [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]
    
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.bytbil.com/bil',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache'
    }

    search_params = {
        'Makes': make,
        'Models': model,
        'VehicleType': 'bil'
    }
    
    if year:
        search_params.update({
            'YearFrom': str(year),
            'YearTo': str(year)
        })

    async with AsyncWebCrawler(
        verbose=True, 
        cookies=cookies,
        headers=headers,
        follow_redirects=True,
        javascript=True
    ) as crawler:
        # First, visit the search page to establish session
        search_url = f"https://www.bytbil.com/bil?{urlencode(search_params)}"
        await crawler.arun(url=search_url)
        
        # Wait a bit to simulate human behavior
        await human_like_delay()
        
        # Now try the API calls
        base_url = "https://www.bytbil.com/api/car/search"
        page = 1
        all_cars = []
        
        while True:
            params = {
                **search_params,
                'PageSize': '100',
                'SortField': 'publishedDate',
                'IsAscending': 'false',
                'Page': str(page)
            }
            
            url = f"{base_url}?{urlencode(params)}"
            
            try:
                await human_like_delay()
                
                result = await crawler.arun(
                    url=url,
                    headers={
                        **headers,
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    }
                )
                
                try:
                    if hasattr(result, 'text'):
                        content = result.text
                    elif hasattr(result, 'content'):
                        content = result.content.decode('utf-8')
                    else:
                        content = str(result)
                    
                    # Debug output
                    print(f"\nResponse headers: {getattr(result, 'headers', 'No headers')}")
                    print(f"Response type: {type(result)}")
                    print(f"First 200 chars of response: {content[:200]}\n")
                    
                    content = content.strip()
                    if not content:
                        raise ValueError("Empty response")
                        
                    data = json.loads(content)
                    
                except json.JSONDecodeError as e:
                    print(f"JSON decode error: {str(e)}")
                    print(f"Response content: {content[:200]}...")
                    break
                
                if not data or not data.get('items'):
                    break
                    
                all_cars.extend(data['items'])
                print(f"Fetched page {page}, got {len(data['items'])} cars")
                
                if len(data['items']) < 100:
                    break
                    
                page += 1
                
                if random.random() < 0.3:
                    headers['User-Agent'] = random.choice(user_agents)
                
            except Exception as e:
                print(f"Error fetching page {page}: {str(e)}")
                await asyncio.sleep(random.uniform(10, 20))
                break

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"cars_{make}_{model}_{timestamp}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_cars, f, ensure_ascii=False, indent=2)
            
        print(f"\nFound {len(all_cars)} cars total")
        print(f"Results saved to {filename}")
        
        return all_cars

async def main():
    cars = await fetch_cars('Tesla', 'Model Y', 2023)
    
    if cars:
        print("\nSample car listing:")
        car = cars[0]
        print(f"Price: {car.get('price')} SEK")
        print(f"Year: {car.get('modelYear')}")
        print(f"Mileage: {car.get('milage')} km")
        print(f"Dealer: {car.get('dealer', {}).get('name')}")

if __name__ == "__main__":
    asyncio.run(main())
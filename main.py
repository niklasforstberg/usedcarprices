import asyncio
import random
import cloudscraper
from fake_useragent import UserAgent
from typing import Tuple


#https://www.recaptcha.net/recaptcha/api.js?onload=recaptchaCallback&render=6Lfq1aQUAAAAAFEQDUblSI0TQm2Zp5Q9VK4tJoE7



async def human_like_delay():
    if random.random() < 0.1:
        delay = random.uniform(8, 15)  # Occasionally take longer breaks
    else:
        delay = random.uniform(2, 7)   # Normal browsing delays
    delay += random.random() * 0.5     # Add some noise
    await asyncio.sleep(delay)

async def get_bytbil_session() -> Tuple[cloudscraper.CloudScraper, dict]:
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'darwin',
            'mobile': False
        }
    )
    
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'User-Agent': UserAgent().chrome
    }
    
    # Initial request to get cookies
    response = scraper.get('https://www.bytbil.com/', headers=headers)
    await human_like_delay()
    
    # First get the reCAPTCHA script
    recaptcha_js = scraper.get(
        'https://www.recaptcha.net/recaptcha/api.js',
        params={
            'onload': 'recaptchaCallback',
            'render': '6Lfq1aQUAAAAAFEQDUblSI0TQm2Zp5Q9VK4tJoE7'
        },
        headers=headers
    )
    await human_like_delay()

    # Then get the actual token
    token_response = scraper.get(
        'https://www.google.com/recaptcha/api2/reload',
        params={
            'k': '6Lfq1aQUAAAAAFEQDUblSI0TQm2Zp5Q9VK4tJoE7'
        },
        headers={
            **headers,
            'Referer': 'https://www.bytbil.com/'
        }
    )
    await human_like_delay()
    
    # Merge all cookies
    all_cookies = {
        **response.cookies,
        **recaptcha_js.cookies,
        **token_response.cookies
    }
    
    return scraper, all_cookies

# Example usage
async def main():
    scraper, cookies = await get_bytbil_session()
    print("Cookies received:")
    for cookie in cookies:
        print(f"{cookie}: {cookies[cookie]}")
    # Future requests will go here
    
if __name__ == "__main__":
    asyncio.run(main())

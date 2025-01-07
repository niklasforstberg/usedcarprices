import json
from urllib.parse import urlparse
from pathlib import Path

def analyze_har(har_path, output_path="interesting_requests.txt"):
    with open(har_path, 'r', encoding='utf-8') as f:
        har_data = json.load(f)
    
    interesting_requests = []
    
    # Skip patterns for non-essential requests
    skip_patterns = [
        'fonts',
        '.woff',
        '.css',
        'google-analytics',
        'googletagmanager',
        'google',
        'cmpv2',
        'trafficgateway.research-int.se',
        'img',
        'doubleclick.net',
        'favicon',
        'https://www.bytbil.com/api/car/count?',
        'adloader'
    ]
    
    print("\nDebug: Scanning requests...")
    
    for entry in har_data['log']['entries']:
        url = entry['request']['url']
        method = entry['request']['method']
        
        print(f"Checking URL: {url}")
        
        # Skip non-essential requests
        if any(pattern in url.lower() for pattern in skip_patterns):
            print(f"Skipping: {url}")
            continue
            
        # Keep bytbil requests
        if 'bytbil.com' in url:
            request_info = [
                f"\n{'='*80}",
                f"Method: {method}",
                f"URL: {url}",
                f"Status: {entry['response']['status']}",
                f"Request Headers:",
                json.dumps(entry['request'].get('headers', []), indent=2),
                "\nResponse Headers:",
                json.dumps(entry['response'].get('headers', []), indent=2),
                f"\nRequest Body:",
                json.dumps(entry['request'].get('postData', {}), indent=2),
                f"\nResponse Body:",
                json.dumps(entry['response'].get('content', {}), indent=2),
                f"{'='*80}\n"
            ]
            interesting_requests.append('\n'.join(request_info))
            print(f"Found interesting request: {url}")
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(interesting_requests))
    
    print(f"\nAnalysis written to {output_path}")
    print(f"Found {len(interesting_requests)} interesting requests")

if __name__ == "__main__":
    analyze_har('bytbil3.har')
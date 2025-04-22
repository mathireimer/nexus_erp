import requests
from bs4 import BeautifulSoup

def test_exchange_rates():
    url = 'https://www.bcp.gov.py/webapps/web/cotizacion/monedas'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        print("Fetching exchange rates from BCP...")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'table'})
            
            if table:
                print("\nExchange Rates:")
                print("-" * 40)
                rows = table.find_all('tr')[1:]  # Skip header row
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        currency = cols[1].text.strip()
                        sell_rate = cols[3].text.strip()
                        print(f"Currency: {currency:<5} | Sell Rate: {sell_rate}")
            else:
                print("Could not find exchange rate table in the response")
                print("Response content:")
                print(response.text[:500])  # Print first 500 characters of response
        else:
            print(f"Failed to fetch rates. Status code: {response.status_code}")
            print("Response content:")
            print(response.text[:500])
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_exchange_rates() 
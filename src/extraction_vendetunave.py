import asyncio
import json
from bs4 import BeautifulSoup
from datetime import datetime
import aiohttp
from src.utils import timer_decorator

BASE_URL = 'https://www.vendetunave.co'
LISTING_URL = f'{BASE_URL}/vehiculos/carrosycamionetas'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Accept-Language': 'es-CO,es;q=0.9',
}


@timer_decorator
async def main(pages, items='all', start_page=1):
    all_rows = []
    page_num = start_page

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        while True:
            url = LISTING_URL if page_num == 1 else f'{LISTING_URL}?page={page_num}'
            print(f'Scraping page {page_num}: {url}')

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        print(f'  HTTP {resp.status}, stopping.')
                        break
                    html = await resp.text()
            except Exception as e:
                print(f'  Request failed: {e}')
                break

            rows = parse_listing_page(html)

            if not rows:
                print('No vehicles found, stopping.')
                break

            if items != 'all':
                rows = rows[:items]

            all_rows.extend(rows)
            print(f'  Got {len(rows)} vehicles (total so far: {len(all_rows)})')

            if pages != 'all' and page_num >= start_page + pages - 1:
                break

            page_num += 1

    return all_rows


def parse_listing_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    script = soup.find('script', id='__NEXT_DATA__')
    if not script:
        return []

    try:
        data = json.loads(script.string)
        vehicles = data['props']['pageProps']['data']['vehicles']
    except (KeyError, json.JSONDecodeError, TypeError):
        return []

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    for v in vehicles:
        vehicle_id = v.get('id')
        link = f"{BASE_URL}/vehiculo/{vehicle_id}" if vehicle_id else None

        city = v.get('labelCiudad')
        dep = v.get('labelDep')
        location = ', '.join(p for p in [city, dep] if p) or None

        specs = {k: v[fk] for k, fk in [
            ('Marca', 'marca'),
            ('Modelo', 'modelo'),
            ('Combustible', 'combustible'),
            ('Transmisión', 'transmision'),
            ('Cilindraje', 'cilindraje'),
            ('Condición', 'condicion'),
            ('Tipo', 'tipoLabel'),
        ] if v.get(fk)}

        precio = v.get('precio')
        km = v.get('kilometraje')

        rows.append({
            'vehicle_id': str(vehicle_id) if vehicle_id is not None else None,
            'product': v.get('title'),
            'price': str(int(precio)) if precio is not None else None,
            'link': link,
            'year': str(v['ano']) if v.get('ano') else None,
            'kilometraje': int(km) if km is not None else None,
            'location': location,
            'plate': v.get('placa'),
            'description': v.get('descripcion'),
            'specs': specs or None,
            '_created': now,
        })

    return rows


if __name__ == '__main__':
    data = asyncio.run(main(pages=1, items=2))
    print(f'Total records: {len(data)}')
    for r in data[:3]:
        print(r)

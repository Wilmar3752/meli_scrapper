import asyncio
from bs4 import BeautifulSoup
import pandas as pd
from src.utils import timer_decorator
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright

BASE_URL = 'https://www.carroya.com'
LISTING_URL = f'{BASE_URL}/vehiculos'

BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--single-process',
]
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

BLOCKED_RESOURCE_TYPES = {'image', 'font', 'media'}
BLOCKED_DOMAINS = ['googletagmanager.com', 'google-analytics.com', 'facebook.net', 'doubleclick.net']


@timer_decorator
async def main(pages, items='all'):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale='es-CO',
        )
        await context.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined});')
        page = await context.new_page()

        async def block_unnecessary(route):
            if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            elif any(domain in route.request.url for domain in BLOCKED_DOMAINS):
                await route.abort()
            else:
                await route.continue_()

        await page.route('**/*', block_unnecessary)

        all_rows = []
        page_num = 1

        while True:
            url = LISTING_URL if page_num == 1 else f'{LISTING_URL}?page={page_num}'
            print(f'Scraping page {page_num}: {url}')

            await page.goto(url, wait_until='networkidle', timeout=60000)
            try:
                await page.wait_for_selector('div.cy-publication-card-portal-ds-milla', timeout=30000)
            except Exception:
                await page.wait_for_timeout(5000)

            rows = parse_listing_page(page_content=await page.content())

            if items != 'all':
                rows = rows[:items]

            for i, row in enumerate(rows):
                link = row.get('link')
                if not link:
                    continue
                print(f'  Detail {i+1}/{len(rows)}: {link[:80]}')
                try:
                    detail = await scrape_detail(page, link)
                    row.update(detail)
                except Exception as e:
                    print(f'  Failed to scrape detail: {e}')

            all_rows.extend(rows)

            if pages != 'all' and page_num >= pages:
                break

            has_next = await has_next_page(page, page_num)
            if not has_next:
                print('No more pages')
                break
            page_num += 1

        await browser.close()

    final_data = pd.DataFrame(all_rows)
    output = json.loads(final_data.to_json(orient='records'))
    return output


async def scrape_detail(page, url):
    await page.goto(url, wait_until='networkidle', timeout=60000)
    try:
        await page.wait_for_selector('div.generalInfo', timeout=15000)
    except Exception:
        await page.wait_for_timeout(3000)

    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    # Extract JSON-LD Product data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            ld = json.loads(script.string)
            if isinstance(ld, dict) and ld.get('@type') == 'Product':
                result['json_ld'] = ld
                break
        except (json.JSONDecodeError, TypeError):
            continue

    # Extract features (specs)
    specs = {}
    features_section = soup.find(class_='features')
    if features_section:
        for feature in features_section.find_all(class_='feature'):
            name_el = feature.find('h5', class_='name')
            value_el = feature.find('h4', class_='description')
            if name_el and value_el:
                specs[name_el.get_text(strip=True)] = value_el.get_text(strip=True)
    if specs:
        result['specs'] = specs

    # Extract seller info
    seller_el = soup.find(class_='cy-seller-detail')
    if seller_el:
        name_el = seller_el.find(class_='cy-seller-detail__name')
        addr_el = seller_el.find(class_='cy-seller-detail__address')
        if name_el:
            result['seller_name'] = name_el.get_text(strip=True)
        if addr_el:
            result['seller_address'] = addr_el.get_text(strip=True)

    return result


async def has_next_page(page, current_page_num):
    btns = await page.query_selector_all('.page-button')
    for btn in btns:
        text = (await btn.inner_text()).strip()
        try:
            if int(text) == current_page_num + 1:
                return True
        except ValueError:
            continue
    return False


def parse_listing_page(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    cards = soup.find_all('div', class_='cy-publication-card-portal-ds-milla')
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for card in cards:
        # Title and link
        anchor = card.find('a', class_='cy-publication-card-portal-ds-milla__publication-basic-data')
        if anchor is None:
            continue
        title_el = anchor.find('h3')
        product_name = title_el.get_text(strip=True) if title_el else None
        href = anchor.get('href', '')
        link = f'{BASE_URL}{href}' if href.startswith('/') else href

        # Price
        price_el = card.find('h4', class_='price')
        price = price_el.get_text(strip=True) if price_el else None

        # Detail tags: location, km, year, plate
        detail_tags = card.find_all('h4', class_='cy-publication-card-portal-ds-milla__publication-detail-tag')
        location = detail_tags[0].get_text(strip=True) if len(detail_tags) > 0 else None
        km = detail_tags[1].get_text(strip=True) if len(detail_tags) > 1 else None
        year = detail_tags[2].get_text(strip=True) if len(detail_tags) > 2 else None
        plate = detail_tags[3].get_text(strip=True) if len(detail_tags) > 3 else None

        # Vehicle ID from card id attribute
        vehicle_id = card.get('id')

        rows.append({
            'vehicle_id': vehicle_id,
            'product': product_name,
            'price': price,
            'link': link,
            'year': year,
            'kilometraje': km,
            'location': location,
            'plate': plate,
            '_created': now,
        })

    return rows


if __name__ == '__main__':
    data = asyncio.run(main(pages=1, items=2))
    print(f'Total records: {len(data)}')
    for r in data[:3]:
        print(r)

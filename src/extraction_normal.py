import asyncio
from bs4 import BeautifulSoup
import pandas as pd
from src.utils import timer_decorator
import json
import requests
from datetime import datetime
from playwright.async_api import async_playwright

BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-infobars',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--lang=es-CO',
    '--window-size=1920,1080',
]
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'

STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['es-CO', 'es', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'});
window.chrome = {runtime: {}};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : originalQuery(parameters);
"""

FREE_PROXY_URL = (
    'https://api.proxyscrape.com/v4/free-proxy-list/get'
    '?request=display_proxies&proxy_format=protocolipport&format=text'
    '&protocol=http&timeout=5000&country=co,br,mx,ar,cl,pe'
)


def _find_working_proxy():
    """Find a free proxy that can reach MeLi without verification challenge."""
    try:
        r = requests.get(FREE_PROXY_URL, timeout=10)
        proxies = [l.strip() for l in r.text.strip().split('\n') if l.strip()]
    except Exception as e:
        print(f'  Failed to fetch proxy list: {e}')
        return None

    print(f'  Testing {len(proxies)} proxies...')
    for proxy_url in proxies:
        try:
            r = requests.get(
                'https://www.mercadolibre.com.co/',
                proxies={'http': proxy_url, 'https': proxy_url},
                timeout=8,
                headers={'User-Agent': USER_AGENT},
            )
            if r.status_code == 200 and 'account-verification' not in r.text:
                print(f'  Working proxy found: {proxy_url}')
                return proxy_url
        except Exception:
            continue

    print('  No working proxy found')
    return None


@timer_decorator
async def main(product, pages, items='all'):
    product = product.lower().strip()
    URLS = {
        'carros': 'https://carros.mercadolibre.com.co/',
        'motos': 'https://motos.mercadolibre.com.co/',
    }
    if product not in URLS:
        raise ValueError(f"product must be 'carros' or 'motos', got '{product}'")
    BASE_URL = URLS[product]

    proxy_url = _find_working_proxy()
    async with async_playwright() as p:
        launch_opts = {'headless': True, 'args': BROWSER_ARGS}
        if proxy_url:
            launch_opts['proxy'] = {'server': proxy_url}
        browser = await p.chromium.launch(**launch_opts)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale='es-CO',
            timezone_id='America/Bogota',
            geolocation={'latitude': 4.711, 'longitude': -74.0721},
            permissions=['geolocation'],
        )
        await context.add_init_script(STEALTH_JS)
        page = await context.new_page()

        await _accept_cookies(page)
        await _navigate_with_verification(page, BASE_URL, product)

        all_rows = []
        page_num = 1

        while True:
            print(f'Scraping page {page_num}: {page.url}')
            rows = parse_listing_page(page_content=await page.content())

            for i, row in enumerate(rows):
                if items != 'all' and len(all_rows) + i >= items:
                    rows = rows[:i]
                    break
                link = row.get('link')
                if not link:
                    continue
                print(f'  Detail {i+1}/{len(rows)}: {link[:80]}...')
                try:
                    detail = await scrape_detail(page, link)
                    row.update(detail)
                except Exception as e:
                    print(f'  Failed to scrape detail: {e}')

            all_rows.extend(rows)

            if pages != 'all' and page_num >= pages:
                break

            has_next = await goto_next_page(page)
            if not has_next:
                print('No more pages')
                break
            page_num += 1

        await browser.close()

    final_data = pd.DataFrame(all_rows)
    output = json.loads(final_data.to_json(orient='records'))
    return output


async def scrape_detail(page, url):
    await page.goto(url, wait_until='domcontentloaded')
    try:
        await page.wait_for_selector('h1', timeout=10000)
    except Exception:
        await page.wait_for_timeout(3000)

    html = await page.content()
    soup = BeautifulSoup(html, 'html.parser')
    result = {}

    # Extract JSON-LD Vehicle data
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            ld = json.loads(script.string)
            if isinstance(ld, dict) and ld.get('@type') == 'Vehicle':
                result['json_ld'] = ld
                break
        except (json.JSONDecodeError, TypeError):
            continue

    # Extract specs table
    specs = {}
    for tr in soup.select('tr.ui-vpp-striped-specs__row'):
        th = tr.find('th')
        td = tr.find('td')
        if th and td:
            specs[th.get_text(strip=True)] = td.get_text(strip=True)
    if specs:
        result['specs'] = specs

    # Extract seller name
    seller_el = soup.select_one('.ui-vip-seller-profile')
    if seller_el:
        name_el = seller_el.select_one('.ui-vip-seller-profile__info-name, .ui-pdp-seller__header__title')
        if name_el:
            result['seller_name'] = name_el.get_text(strip=True)

    # Extract description
    desc_el = soup.select_one('.ui-pdp-description__content')
    if desc_el:
        result['description'] = desc_el.get_text(strip=True)

    return result


async def _accept_cookies(page):
    await page.goto('https://www.mercadolibre.com.co/', wait_until='domcontentloaded')
    await page.wait_for_timeout(2000)
    try:
        btn = page.get_by_role('button', name='Aceptar cookies')
        if await btn.count() > 0:
            await btn.click()
            await page.wait_for_timeout(1000)
    except Exception:
        pass


async def _navigate_with_verification(page, url, product, max_retries=3):
    # Strategy 1: Search from homepage like a real user
    print(f'  Searching for "{product}" from homepage...')
    search_input = page.locator('input[name="as_word"]')
    if await search_input.count() > 0:
        await search_input.fill(product)
        await search_input.press('Enter')
        try:
            await page.wait_for_selector('div.ui-search-result__wrapper', timeout=15000)
            print(f'  Search worked: {page.url}')
            return
        except Exception:
            print(f'  Search did not load results, trying direct URL...')

    # Strategy 2: Direct URL with retries
    for attempt in range(max_retries):
        await page.goto(url, wait_until='networkidle')

        if 'account-verification' not in page.url and 'gz/' not in page.url:
            break

        print(f'  Verification challenge detected (attempt {attempt+1}): {page.url}')
        try:
            await page.wait_for_url(
                lambda u: 'account-verification' not in u and 'gz/' not in u,
                timeout=30000,
            )
            print(f'  Challenge resolved, redirected to: {page.url}')
            break
        except Exception:
            print(f'  Challenge did not redirect, retrying...')
            continue

    try:
        await page.wait_for_selector('div.ui-search-result__wrapper', timeout=15000)
    except Exception:
        await page.wait_for_timeout(5000)
    print(f'  Navigated to: {page.url}')


async def goto_next_page(page):
    next_btn = page.locator('li.andes-pagination__button--next a')
    if await next_btn.count() == 0:
        return False
    is_disabled = await page.locator('li.andes-pagination__button--next.andes-pagination__button--disabled').count()
    if is_disabled > 0:
        return False
    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
    await page.wait_for_timeout(500)
    await next_btn.click()
    try:
        await page.wait_for_selector('div.ui-search-result__wrapper', timeout=15000)
    except Exception:
        await page.wait_for_timeout(5000)
    return True


def parse_listing_page(page_content):
    s = BeautifulSoup(page_content, 'html.parser')
    cards = s.find_all('div', attrs={"class": "ui-search-result__wrapper"})
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for card in cards:
        title_el = card.find('h3', attrs={"class": "poly-component__title-wrapper"})
        if title_el is None:
            continue
        product_name = title_el.text.strip()
        link_el = title_el.find('a')
        link = link_el.get('href') if link_el else None
        price_el = card.find('span', attrs={"class": "andes-money-amount__fraction"})
        price = price_el.text.replace('.', '') if price_el else None
        attrs_list = card.find_all('li', attrs={'class': 'poly-attributes_list__item'})
        year = attrs_list[0].text.strip() if len(attrs_list) > 0 else None
        km = attrs_list[1].text.strip() if len(attrs_list) > 1 else None
        loc_el = card.find('span', attrs={'class': 'poly-component__location'})
        location = loc_el.text.strip() if loc_el else None
        rows.append({
            'product': product_name,
            'price': price,
            'link': link,
            'years': year,
            'kilometraje': km,
            'locations': location,
            '_created': now,
        })

    return rows


if __name__ == '__main__':
    data = asyncio.run(main(product='carros', pages=1, items=2))
    print(f'Total records: {len(data)}')
    for r in data[:3]:
        print(r)

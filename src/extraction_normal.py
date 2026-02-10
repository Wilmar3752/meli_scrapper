import asyncio
from bs4 import BeautifulSoup
import pandas as pd
from src.utils import timer_decorator, generate_proxy_url
import json
from datetime import datetime
from playwright.async_api import async_playwright

BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
]
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'


@timer_decorator
async def main(product, pages):
    if product == 'carros':
        BASE_URL = 'https://carros.mercadolibre.com.co/'
    elif product == 'motos':
        BASE_URL = 'https://motos.mercadolibre.com.co/'

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale='es-CO',
        )
        await context.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined});')
        page = await context.new_page()

        await _accept_cookies(page)

        await page.goto(BASE_URL, wait_until='domcontentloaded')
        try:
            await page.wait_for_selector('div.ui-search-result__wrapper', timeout=15000)
        except Exception:
            await page.wait_for_timeout(5000)

        list_df = []
        page_num = 1

        while True:
            print(f'Scraping page {page_num}: {page.url}')
            df = parse_current_page(page_content=await page.content())
            list_df.append(df)

            if pages != 'all' and page_num >= pages:
                break

            has_next = await goto_next_page(page)
            if not has_next:
                print('No more pages')
                break
            page_num += 1

        await browser.close()

    final_data = pd.concat(list_df)
    output = json.loads(final_data.to_json(orient='records'))
    return output


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


def parse_current_page(page_content):
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

    return pd.DataFrame(rows)


if __name__ == '__main__':
    data = asyncio.run(main(product='carros', pages=2))
    print(f'Total records: {len(data)}')
    for r in data[:3]:
        print(r)

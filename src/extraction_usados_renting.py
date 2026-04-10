import asyncio
import re
import io
import tempfile
from bs4 import BeautifulSoup
import pandas as pd
from src.utils import timer_decorator, clean_price, clean_km
import json
import os
from datetime import datetime
from playwright.async_api import async_playwright
import aiohttp
try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False

BASE_URL = 'https://www.usadosrentingcolombia.com'
LISTING_URL = f'{BASE_URL}/category/root'
PAGE_SIZE = 15

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
async def main(pages, items='all', start_page=1):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale='es-CO',
        )
        await context.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined});')

        async def block_unnecessary(route):
            if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
                await route.abort()
            elif any(domain in route.request.url for domain in BLOCKED_DOMAINS):
                await route.abort()
            else:
                await route.continue_()

        await context.route('**/*', block_unnecessary)
        page = await context.new_page()

        semaphore = asyncio.Semaphore(5)

        async def scrape_detail_bounded(row):
            link = row.get('link')
            if not link:
                return
            async with semaphore:
                detail_page = await context.new_page()
                try:
                    detail = await scrape_detail(detail_page, link)
                    row.update(detail)
                except Exception as e:
                    print(f'  Failed to scrape detail {link[:80]}: {e}')
                finally:
                    await detail_page.close()

        all_rows = []
        page_num = start_page

        while True:
            offset = (page_num - 1) * PAGE_SIZE
            url = LISTING_URL if offset == 0 else f'{LISTING_URL}?offset={offset}'
            print(f'Scraping page {page_num} (offset={offset}): {url}')

            await page.goto(url, wait_until='networkidle', timeout=60000)
            try:
                await page.wait_for_selector('a[href^="/product/"]', timeout=30000)
            except Exception:
                await page.wait_for_timeout(5000)

            # Scroll to trigger lazy loading
            for _ in range(5):
                await page.evaluate('window.scrollBy(0, window.innerHeight)')
                await page.wait_for_timeout(800)
            await page.evaluate('window.scrollTo(0, 0)')

            rows = parse_listing_page(page_content=await page.content())

            if not rows:
                print('No cards found on page, stopping.')
                break

            if items != 'all':
                rows = rows[:items]

            print(f'  Scraping {len(rows)} details in parallel (max 5 concurrent)...')
            await asyncio.gather(*[scrape_detail_bounded(row) for row in rows])

            all_rows.extend(rows)

            if pages != 'all' and page_num >= start_page + pages - 1:
                break

            has_next = await has_next_page(page)
            if not has_next:
                print('No more pages.')
                break
            page_num += 1

        await browser.close()

    final_data = pd.DataFrame(all_rows)
    output = json.loads(final_data.to_json(orient='records'))
    return output


async def _extract_linea_from_pdf(page):
    """Find the 'Descargar' link, download the PDF, and extract the 'Línea' field."""
    if not _PDFPLUMBER_AVAILABLE:
        return None
    try:
        # Find PDF URL in rendered DOM
        pdf_url = await page.evaluate('''() => {
            const all = Array.from(document.querySelectorAll('a'));
            for (const a of all) {
                const href = a.href || '';
                const text = a.textContent.trim().toLowerCase();
                if (href.toLowerCase().includes('.pdf') || href.toLowerCase().includes('/pdf')) return href;
                if (text.includes('descargar') && href) return href;
            }
            return null;
        }''')

        pdf_bytes = None

        if pdf_url and not pdf_url.startswith('blob:') and pdf_url.startswith('http'):
            # Direct URL — download with aiohttp using page cookies
            cookies = await page.context.cookies()
            cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    pdf_url,
                    headers={'Cookie': cookie_str, 'User-Agent': USER_AGENT},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        pdf_bytes = await resp.read()
        else:
            # Fallback: intercept Playwright download via click
            btn = page.locator('a:has-text("Descargar"), button:has-text("Descargar"), a:has-text("descargar"), button:has-text("descargar")')
            if await btn.count() == 0:
                return None
            async with page.expect_download(timeout=20000) as dl_info:
                await btn.first.click()
            download = await dl_info.value
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp_path = tmp.name
            await download.save_as(tmp_path)
            with open(tmp_path, 'rb') as f:
                pdf_bytes = f.read()
            os.unlink(tmp_path)

        if not pdf_bytes:
            return None

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = '\n'.join(p.extract_text() or '' for p in pdf.pages)

        # Search for "Línea" / "Linea" label followed by its value
        match = re.search(r'[Ll][ií]nea\s*[:\-]?\s*(.+?)(?:\n|$)', text)
        if match:
            return match.group(1).strip()
    except Exception as e:
        print(f'  PDF linea extraction failed: {e}')
    return None


async def scrape_detail(page, url):
    await page.goto(url, wait_until='networkidle', timeout=60000)
    # Wait for the vehicle detail section to render
    try:
        await page.wait_for_selector('text=Detalle del vehículo', timeout=15000)
    except Exception:
        await page.wait_for_timeout(4000)

    # Extract label/value pairs from the rendered DOM.
    # The page uses React cards where a label (e.g. "Motor") sits above its value (e.g. "1368").
    # We find all elements whose text matches known labels, then grab the next sibling's text.
    known_labels = [
        'Motor', 'Transmisión', 'Combustible', 'Ubicación', 'Kilometraje', 'Modelo',
        'Tipo de vehículo', 'Color', 'Marca', 'Tapicería', 'Ciudad matrícula',
        'SOAT', 'Tecnomecánica', 'Placa', 'Descripción',
    ]

    specs = await page.evaluate('''(labels) => {
        const result = {};
        // Walk all elements, find those whose trimmed text matches a label exactly,
        // then look for a sibling or nearby element with the value.
        const allEls = Array.from(document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6'));
        for (const el of allEls) {
            const text = el.textContent.trim();
            if (!labels.includes(text)) continue;
            // Check next sibling element
            let sib = el.nextElementSibling;
            if (sib) {
                const val = sib.textContent.trim();
                if (val && val !== text) {
                    result[text] = val;
                    continue;
                }
            }
            // Check parent's next sibling (label and value may be in separate children of a card)
            const parent = el.parentElement;
            if (parent) {
                const parentSib = parent.nextElementSibling;
                if (parentSib) {
                    const val = parentSib.textContent.trim();
                    if (val && val !== text) {
                        result[text] = val;
                        continue;
                    }
                }
                // Value may be a sibling within the same parent
                const siblings = Array.from(parent.children);
                const idx = siblings.indexOf(el);
                if (idx !== -1 && idx + 1 < siblings.length) {
                    const val = siblings[idx + 1].textContent.trim();
                    if (val && val !== text) {
                        result[text] = val;
                    }
                }
            }
        }
        return result;
    }''', known_labels)

    result = {}
    if specs:
        # Store all label/value pairs in a specs dict (same pattern as Carroya/Meli)
        result['specs'] = {k: v for k, v in specs.items() if v}
        # Expose description at top level (matches Meli's 'description' field)
        if specs.get('Descripción'):
            result['description'] = specs['Descripción']

    # Extract vehicle line from PDF ficha técnica — overwrites listing product name
    linea = await _extract_linea_from_pdf(page)
    if linea:
        result['product'] = linea

    return result


async def has_next_page(page):
    # Look for a "next" pagination button that is not disabled
    try:
        # Common aria pattern for next-page buttons
        next_btn = page.locator('button[aria-label*="siguiente"], button[aria-label*="next"], a[aria-label*="siguiente"], a[aria-label*="next"]')
        count = await next_btn.count()
        if count > 0:
            is_disabled = await next_btn.first.get_attribute('disabled')
            return is_disabled is None
    except Exception:
        pass

    # Fallback: check if a link with ?offset= pointing to the next page exists
    try:
        links = page.locator('a[href*="offset="]')
        count = await links.count()
        return count > 0
    except Exception:
        return False


def _parse_km_string(km_str):
    """Parse '352.073 km | 2007 | Manual | *****5' into (km, year, plate)."""
    if not km_str:
        return None, None, None
    parts = [p.strip() for p in km_str.split('|')]
    km = clean_km(parts[0]) if len(parts) > 0 else None
    year = parts[1] if len(parts) > 1 else None
    plate = parts[3] if len(parts) > 3 else None
    return km, year or None, plate or None


def parse_listing_page(page_content):
    soup = BeautifulSoup(page_content, 'html.parser')
    cards = soup.find_all('a', href=lambda h: h and h.startswith('/product/'))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = []
    for card in cards:
        href = card.get('href', '')
        link = f'{BASE_URL}{href}'
        vehicle_id = href.replace('/product/', '').strip('/')

        texts = [t.strip() for t in card.stripped_strings if t.strip()]

        product_name = texts[0] if texts else None
        raw_price = None
        raw_km_string = None
        location = None

        for text in texts:
            lower = text.lower()
            if '$' in text or 'cop' in lower:
                raw_price = text
            elif 'km' in lower and '|' in text:
                raw_km_string = text
            elif any(city in lower for city in ('bogot', 'medell', 'cali', 'barranquilla', 'cartagena', 'bucaramanga', 'pereira')):
                location = text

        price = clean_price(raw_price)
        km, year, plate = _parse_km_string(raw_km_string)

        rows.append({
            'vehicle_id': vehicle_id,
            'product': product_name,
            'price': price,
            'link': link,
            'year': year,
            'kilometraje': km,
            'location': location,
            'plate': plate,
            'linea': None,
            '_created': now,
        })

    return rows


if __name__ == '__main__':
    data = asyncio.run(main(pages=1, items=2))
    print(f'Total records: {len(data)}')
    for r in data[:3]:
        print(r)

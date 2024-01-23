import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from src.utils import async_timer_decorator, generate_proxy_url
import aiohttp
import asyncio
import json

BASE_URL = 'https://listado.mercadolibre.com.co'

@async_timer_decorator
async def main(product):
    list_df = []
    initial_df, follow = await organize_page_data(product=product)
    list_df.append(initial_df)
    while True:
        print('follow_page: ', follow)
        follow_df, follow = await organize_page_data(url=follow)
        list_df.append(follow_df)
        follow_df.rename(columns={None:product}, inplace=True)
        if follow is None:
            break

    final_data = pd.concat(list_df)
    output = json.loads(final_data.to_json(orient='records'))
    return output
        
async def organize_page_data(url: str = BASE_URL ,product= None):
    s = await get_soup_by_url(url=url, product=product)
    products = get_all_product_names_for_page(s)
    follow = None
    try:
        follow = get_follow_page(s)
    except:
        print('follow page not found')    
    prices = get_all_product_prices_for_page(s)
    urls = get_all_product_urls_for_page(s)
    years = get_year(s)
    kilometros = get_km(s)
    locations = get_location(s)
    output_dict = {'product':products, 
                   'price':prices,
                   'link':urls,
                   'years': years,
                   'kilometraje':kilometros,
                   'locations': locations}
    
    return pd.DataFrame(output_dict), follow


async def get_soup_by_url(url, product=None):
    proxy = generate_proxy_url()
    if product is None:
        url = url
    else:
        url = f'{url}/{product}'
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, proxy = proxy) as response:
                s = BeautifulSoup(await response.text(encoding='utf-8', errors='ignore'), 'html.parser')
                return s
        except aiohttp.client_exceptions.ClientConnectorSSLError:
            print("Failed to establish a secure connection due to SSL error.")
            return None
        except aiohttp.client_exceptions.ServerDisconnectedError:
            print("Server disconnected unexpectedly.")
            return None
        except aiohttp.client_exceptions.ClientHttpProxyError:
            print("Failed to connect through proxy.")
            return None
def get_all_product_names_for_page(s):
    product_names = s.find_all('h2', attrs= {"class":"ui-search-item__title"})
    product_names = [v.text for v in product_names]
    return product_names

def get_all_product_prices_for_page(s):
    divs  = s.find_all('div', attrs= {"class":"ui-search-result__wrapper"})
    prices = [int(div.find_all('span',  attrs= {"class":"andes-money-amount__fraction"})[0].text.replace('.','')) for div in divs]
    return prices

def get_follow_page(s):
    follow_page = [div.find('a')['href']
          for div in s.find_all('li', attrs={"class":"andes-pagination__button andes-pagination__button--next"}) 
          if div.find('a') is not None][0]
    return follow_page

def get_all_product_urls_for_page(s):
    product_url = s.find_all('a', attrs= {"class":"ui-search-item__group__element ui-search-link__title-card ui-search-link"})
    product_url = [h.get('href') for h in product_url]
    return product_url

def get_year(s):
    soup = s.find_all('li', attrs={'class': 'ui-search-card-attributes__attribute'})
    year = [x.text for x in soup[::2]]
    return year
def get_km(s):
    soup = s.find_all('li', attrs={'class': 'ui-search-card-attributes__attribute'})
    km = [x.text for x in soup[1::2]]
    return km
def get_location(s):
    soup = s.find_all('span', attrs={'class': 'ui-search-item__group__element ui-search-item__location'})
    location = [x.text for x in soup]
    return location

if __name__ == '__main__':
    data = asyncio.run(main(product='carro'))
    print(data)

import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from src.utils import timer_decorator, async_timer_decorator, run_async, async_apply
import aiohttp
import asyncio
import json

BASE_URL = 'https://listado.mercadolibre.com.co'

@async_timer_decorator
async def main(product):
    list_df = []
    initial_df, follow = await organize_page_data(product=product)
    tasks = [get_vehicle_info(x) for x in initial_df['link']]
    initial_df[f'{product}_info'] = await asyncio.gather(*tasks)
    list_df.append(initial_df)
    # while True:
    #     print('follow_page: ', follow)
    #     follow_df, follow = await organize_page_data(url=follow)
    #     follow_df['vehicle_info'] = follow_df['link'].apply(get_vehicle_info)
    #     list_df.append(follow_df)
    #     follow_df.rename(columns={None:product}, inplace=True)
    #     print(follow_df.columns)
    #     if follow is None:
    #         break
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
    output_dict = {'product':products, 'price':prices ,'link':urls}
    return pd.DataFrame(output_dict), follow


async def get_soup_by_url(url, product=None):
   if product is None:
       url = url
   else:
       url = f'{url}/{product}'
   async with aiohttp.ClientSession() as session:
       async with session.get(url) as response:
           s = BeautifulSoup(await response.text(encoding='utf-8', errors='ignore'), 'html.parser')
           return s

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

async def get_vehicle_info(url):
   s = await get_soup_by_url(url)
   try:
       text = s.find_all('span', attrs= {'class':'ui-pdp-subtitle'})[0].text.replace('.', '')
   except IndexError:
       text = ''
   parts = text.split(' · ')
   location = ''
   pub_number = ''
   try:
       location = s.find('p', attrs = {'class':'ui-seller-info__status-info__subtitle'}).text
   except AttributeError:
       pass
   try:
       pub_number = s.find_all('span', attrs= {'class':'ui-pdp-color--BLACK ui-pdp-family--SEMIBOLD'})[0].text.replace('#','')
   except IndexError:
       pass
   
   year = ''
   kilometrage = ''
   publication_date = ''
   
   for i, part in enumerate(parts):
       try:
           split_part = part.split(' | ')
           
           if i == 0:
               year = split_part[0]
               kilometrage = split_part[1].replace('km', '')
           elif i == 1:
               publication_date = part
       except IndexError:
           print(f"Part {i} does not contain enough elements")
   
   output_dict = {
       "Year": year,
       "Kilometrage": kilometrage,
       "Publication Date": publication_date,
       "Location": location,
       "Pub Number": pub_number,
       "Created At": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   }

   return output_dict


if __name__ == '__main__':
    data = asyncio.run(main(product='carro'))
    print(data)

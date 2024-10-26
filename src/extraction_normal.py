import requests
from bs4 import BeautifulSoup
import pandas as pd
from src.utils import timer_decorator, generate_proxy_url
import json
from datetime import datetime


BASE_URL = 'https://listado.mercadolibre.com.co'

@timer_decorator
def main(product, pages):
    list_df = []
    initial_df, follow = organize_page_data(product=product)
    list_df.append(initial_df)
    if pages == 'all':
        while True:
            follow_df, follow = organize_page_data(url=follow)
            list_df.append(follow_df)
            follow_df.rename(columns={None:product}, inplace=True)
            if follow is None:
                break
    elif isinstance(pages, int):
        for _ in range(pages - 1): # subtract 1 because we have already scraped the first page
            follow_df, follow = organize_page_data(url=follow)
            list_df.append(follow_df)
            follow_df.rename(columns={None:product}, inplace=True)
            if follow is None:
                break
    final_data = pd.concat(list_df)
    output = json.loads(final_data.to_json(orient='records'))
    return output

def organize_page_data(url: str = BASE_URL ,product= None):
    s = get_soup_by_url(url=url, product=product)
    products = get_all_product_names_for_page(s)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                   'locations': locations,
                   '_created': now}
    return pd.DataFrame(output_dict), follow


def get_soup_by_url(url, product: str = None):
    # proxy = generate_proxy_url()
    # proxies = {'http': proxy,
    #            'https': proxy}
    if product is None:
        url = url
    else:
        url = f'{url}/{product}'
    r = requests.get(url=url)
    s = BeautifulSoup(r.content, 'html.parser')
    return s


def get_all_product_names_for_page(s):
    product_names = s.find_all('h2', attrs= {"class":"poly-box"})
    product_names = [v.text for v in product_names]
    return product_names

def get_all_product_prices_for_page(s):
    divs  = s.find_all('div', attrs= {"class":"ui-search-result__wrapper"})
    prices = [div.find_all('span',  attrs= {"class":"andes-money-amount__fraction"})[0].text.replace('.','') for div in divs]
    return prices

def get_follow_page(s):
    follow_page = [div.find('a')['href']
          for div in s.find_all('li', attrs={"class":"andes-pagination__button andes-pagination__button--next"}) 
          if div.find('a') is not None][0]
    return follow_page

def get_all_product_urls_for_page(s):
    product_url = s.find_all('h2', attrs= {"class":"poly-box poly-component__title"})
    product_url = [h.find("a").get('href') for h in product_url]
    return product_url

def get_year(s):
    soup = s.find_all('li', attrs={'class': 'poly-attributes-list__item poly-attributes-list__separator'})
    year = [x.text for x in soup[::2]]
    return year
def get_km(s):
    soup = s.find_all('li', attrs={'class': 'poly-attributes-list__item poly-attributes-list__separator'})
    km = [x.text for x in soup[1::2]]
    return km
def get_location(s):
    soup = s.find_all('span', attrs={'class': 'poly-component__location'})
    location = [x.text for x in soup]
    return location


if __name__ == '__main__':
    data = main(product='carros', pages=1)
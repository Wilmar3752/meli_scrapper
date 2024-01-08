import requests
from bs4 import BeautifulSoup
import pandas as pd

def main(product):
    list_df = []
    initial_df, follow = organize_page_data(product=product)
    list_df.append(initial_df)
    while True:
        print('follow_page: ', follow)
        follow_df, follow = organize_page_data(url=follow)
        list_df.append(follow_df)
        follow_df.rename(columns={None:product}, inplace=True)
        print(follow_df.columns)
        if follow is None:
            break
    return pd.concat(list_df)  
        
def organize_page_data(url: str = 'https://listado.mercadolibre.com.co' ,product= None):
    s = get_soup_by_url(url=url, product=product)
    products = get_all_product_names_for_page(s)
    follow = None
    try:
        follow = get_follow_page(s)
    except:
        print('follow page not found')    
    prices = get_all_product_prices_for_page(s)
    urls = get_all_product_urls_for_page(s)
    output_dict = {product:products, 'price':prices ,'link':urls}
    return pd.DataFrame(output_dict), follow


def get_soup_by_url(url, product: str = None):
    if product is None:
        url = url
    else:
        url = f'{url}/{product}'
    r = requests.get(url=url)
    s = BeautifulSoup(r.content, 'html.parser')
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


if __name__ == '__main__':
    data = main(product='carros')
    data.to_csv('final_data.csv')
    

import requests
from bs4 import BeautifulSoup
import pandas as pd

def get_meli_soup_by_product(url: str = 'https://listado.mercadolibre.com.co', product: str = 'carros'):
    url = f'{url}/{product}'
    r = requests.get(url=url)
    s = BeautifulSoup(r.content, 'html.parser')
    return s


if __name__ == '__main__':
    s = get_meli_soup_by_product()
    print(s)

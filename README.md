---
title: Scraper
emoji: 📈
colorFrom: yellow
colorTo: yellow
sdk: docker
pinned: false
license: mit
---

# MeLi Scraper
Web scrapping proyect for vehicle prices in Colombia. To Mercado Libre page with educational focus
## Locally request
Please create your virtual environment before, for example
```bash
python3 -m venv myenv
source myenv/bin/activate
```
Then run
```bash
PYTHONPATH=$PWD
pip install -r requirements.txt
python src/extraction.py
```

## API
To run the API for this project please run
```bash
docker compose up
```



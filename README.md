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
Create your virtual environment with [uv](https://docs.astral.sh/uv/) and install dependencies:
```bash
uv venv
# Add automatic PYTHONPATH to activate script
cat >> .venv/bin/activate << 'EOF'

# set PYTHONPATH to project root
if ! [ -z "${PYTHONPATH+_}" ] ; then
    _OLD_VIRTUAL_PYTHONPATH="$PYTHONPATH"
fi
PYTHONPATH="$(dirname "$VIRTUAL_ENV")"
export PYTHONPATH
EOF
source .venv/bin/activate
uv pip install -r requirements.txt
```
Then run the scraper:
```bash
python src/extraction_normal.py
```

## API
To run the API for this project please run
```bash
docker compose up
```



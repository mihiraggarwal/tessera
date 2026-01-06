# India Health Voronoi Locator

Interactive Streamlit app that:
- Loads health facility locations from `geocode_health_centre.csv`
- Samples up to 1000 facilities
- Builds a Voronoi diagram over India
- Lets you click on the map to see the nearest facility and simulate adding a new one

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app.py

# RouteAI — Fleet Dispatch Optimizer
## Setup (run these once)
```
pip install -r requirements.txt
```
## Run
```
python app.py
```
Then open: http://localhost:5000

## Demo flow (3 minutes)
1. Page loads → Click "Load Normal State" → 8 colored routes appear on Chennai map
2. Click "Simulate RFID Scan" a few times → inventory log updates bottom right
3. Click "INJECT DISRUPTION (NH48)" → 1.8s spinner → map redraws → NH48 turns red → new magenta routes appear → Gemini alert shows
4. Drag α/β/γ sliders → explain multi-criteria optimization to judge
5. Point to CO2 saved counter top right

## Structure
- vrp_solver.py  → Dijkstra + greedy VRP + Gemini fuzzy mapper
- app.py         → Flask backend, REST endpoints
- templates/     → Leaflet.js dashboard

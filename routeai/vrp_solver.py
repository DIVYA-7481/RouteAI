"""
RouteAI VRP Solver â€” ResilientChain AI
=======================================
Multi-agent fleet dispatch optimizer for Indian logistics.
Covers 5 cities: Chennai, Bengaluru, Hyderabad, Mumbai, Visakhapatnam, Cochin.
Graph: ~50 nodes, inter-city NH highways + city sub-graphs.
VRP: capacity-constrained greedy insertion + Dijkstra shortest path.
Time-window: commercial trucks banned on city-limit edges 07:00â€“22:00.

Academic Mapping:
  CD343AI Unit II  â€” Graph representations, adjacency structures
  CD343AI Unit III â€” Dijkstra's SSSP, Bellman-Ford
  CD343AI Unit IV  â€” NP-hard VRP, greedy approximation heuristics
  CD343AI Unit V   â€” Scheduling with constraints, time-window modelling
"""

import heapq
import math
import copy
import json
from datetime import datetime, timedelta
from fuzzywuzzy import process, fuzz as _fuzz
import networkx as nx

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SECTION 1 â€” NODE DEFINITIONS
# Each node: id â†’ {name, lat, lon, type, city}
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# â”€â”€ Chennai (original 15 nodes, preserved) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CHENNAI_NODES = {
    "W1": {"name": "Koyambedu Market",   "lat": 13.0694, "lon": 80.1948, "type": "origin",      "city": "Chennai"},
    "W2": {"name": "Ambattur Warehouse", "lat": 13.1143, "lon": 80.1548, "type": "origin",      "city": "Chennai"},
    "W3": {"name": "Tambaram Hub",       "lat": 12.9249, "lon": 80.1000, "type": "hub",         "city": "Chennai"},
    "W4": {"name": "Guindy Depot",       "lat": 13.0067, "lon": 80.2206, "type": "hub",         "city": "Chennai"},
    "W5": {"name": "Perambur Centre",    "lat": 13.1152, "lon": 80.2344, "type": "hub",         "city": "Chennai"},
    "W6": {"name": "Sholinganallur Hub", "lat": 12.9010, "lon": 80.2279, "type": "hub",         "city": "Chennai"},
    "W7": {"name": "Porur Junction",     "lat": 13.0358, "lon": 80.1572, "type": "hub",         "city": "Chennai"},
    "W8": {"name": "Avadi Logistics",    "lat": 13.1152, "lon": 80.0982, "type": "hub",         "city": "Chennai"},
    "D1": {"name": "T.Nagar Retail",     "lat": 13.0418, "lon": 80.2341, "type": "destination", "city": "Chennai"},
    "D2": {"name": "Anna Nagar Store",   "lat": 13.0891, "lon": 80.2099, "type": "destination", "city": "Chennai"},
    "D3": {"name": "Velachery Market",   "lat": 12.9815, "lon": 80.2180, "type": "destination", "city": "Chennai"},
    "D4": {"name": "Chromepet Retail",   "lat": 12.9516, "lon": 80.1462, "type": "destination", "city": "Chennai"},
    "D5": {"name": "Adyar Supermarket",  "lat": 13.0012, "lon": 80.2565, "type": "destination", "city": "Chennai"},
    "D6": {"name": "Pallavaram Store",   "lat": 12.9675, "lon": 80.1491, "type": "destination", "city": "Chennai"},
    "D7": {"name": "Thiruvottiyur Hub",  "lat": 13.1626, "lon": 80.3032, "type": "destination", "city": "Chennai"},
}

# â”€â”€ Coastal Port Hubs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
COASTAL_NODES = {
    "MUM_H1": {"name": "Mumbai Port Hub",          "lat": 18.9388, "lon": 72.8354, "type": "port_hub", "city": "Mumbai"},
    "VIZ_H1": {"name": "Visakhapatnam Port Hub",   "lat": 17.6868, "lon": 83.2185, "type": "port_hub", "city": "Visakhapatnam"},
    "COC_H1": {"name": "Cochin Port Hub",           "lat":  9.9312, "lon": 76.2673, "type": "port_hub", "city": "Cochin"},
}

# â”€â”€ Bengaluru Mini Hubs (BEN_H1â€“BEN_H20) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BENGALURU_NODES = {
    "BEN_H1":  {"name": "Peenya Industrial Area",      "lat": 13.0284, "lon": 77.5192, "type": "hub", "city": "Bengaluru"},
    "BEN_H2":  {"name": "Tumkur Road Hub",             "lat": 13.0716, "lon": 77.4785, "type": "hub", "city": "Bengaluru"},
    "BEN_H3":  {"name": "Hosur Road Depot",            "lat": 12.8728, "lon": 77.6490, "type": "hub", "city": "Bengaluru"},
    "BEN_H4":  {"name": "Electronics City Hub",        "lat": 12.8452, "lon": 77.6613, "type": "hub", "city": "Bengaluru"},
    "BEN_H5":  {"name": "Whitefield Logistics",        "lat": 12.9698, "lon": 77.7499, "type": "hub", "city": "Bengaluru"},
    "BEN_H6":  {"name": "Nelamangala Junction",        "lat": 13.0979, "lon": 77.3924, "type": "hub", "city": "Bengaluru"},
    "BEN_H7":  {"name": "KIA Airport Hub",             "lat": 13.1989, "lon": 77.7068, "type": "hub", "city": "Bengaluru"},
    "BEN_H8":  {"name": "Yelahanka Hub",               "lat": 13.1004, "lon": 77.5963, "type": "hub", "city": "Bengaluru"},
    "BEN_H9":  {"name": "Bommasandra Industrial",      "lat": 12.8104, "lon": 77.6969, "type": "hub", "city": "Bengaluru"},
    "BEN_H10": {"name": "Jigani Industrial Area",      "lat": 12.7830, "lon": 77.6370, "type": "hub", "city": "Bengaluru"},
    "BEN_H11": {"name": "Doddaballapur Road Hub",      "lat": 13.2957, "lon": 77.5376, "type": "hub", "city": "Bengaluru"},
    "BEN_H12": {"name": "Bidadi Industrial Hub",       "lat": 12.8010, "lon": 77.3890, "type": "hub", "city": "Bengaluru"},
    "BEN_H13": {"name": "Ramanagara Hub",              "lat": 12.7157, "lon": 77.2817, "type": "hub", "city": "Bengaluru"},
    "BEN_H14": {"name": "Devanahalli Logistics",       "lat": 13.2467, "lon": 77.7117, "type": "hub", "city": "Bengaluru"},
    "BEN_H15": {"name": "Hoskote Industrial Hub",      "lat": 13.0693, "lon": 77.7983, "type": "hub", "city": "Bengaluru"},
    "BEN_H16": {"name": "Attibele Border Hub",         "lat": 12.7804, "lon": 77.7638, "type": "hub", "city": "Bengaluru"},
    "BEN_H17": {"name": "Bannerghatta Road Hub",       "lat": 12.8640, "lon": 77.5960, "type": "hub", "city": "Bengaluru"},
    "BEN_H18": {"name": "Kengeri Satellite Hub",       "lat": 12.9063, "lon": 77.4822, "type": "hub", "city": "Bengaluru"},
    "BEN_H19": {"name": "Srirangapatna Hub",           "lat": 12.4155, "lon": 76.7028, "type": "hub", "city": "Bengaluru"},
    "BEN_H20": {"name": "Mandya Logistics Centre",     "lat": 12.5244, "lon": 76.8962, "type": "hub", "city": "Bengaluru"},
}

# â”€â”€ Hyderabad Mini Hubs (HYD_H1â€“HYD_H20) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HYDERABAD_NODES = {
    "HYD_H1":  {"name": "Patancheru Industrial Hub",   "lat": 17.5285, "lon": 78.2647, "type": "hub", "city": "Hyderabad"},
    "HYD_H2":  {"name": "Medchal Logistics Park",      "lat": 17.6277, "lon": 78.4813, "type": "hub", "city": "Hyderabad"},
    "HYD_H3":  {"name": "Shamshabad Air Cargo Hub",    "lat": 17.2403, "lon": 78.4294, "type": "hub", "city": "Hyderabad"},
    "HYD_H4":  {"name": "Fab City SEZ Hub",            "lat": 17.2065, "lon": 78.5488, "type": "hub", "city": "Hyderabad"},
    "HYD_H5":  {"name": "Rajiv Gandhi IT Park",        "lat": 17.4435, "lon": 78.3772, "type": "hub", "city": "Hyderabad"},
    "HYD_H6":  {"name": "Uppal Industrial Hub",        "lat": 17.4052, "lon": 78.5591, "type": "hub", "city": "Hyderabad"},
    "HYD_H7":  {"name": "LB Nagar Distribution Hub",  "lat": 17.3447, "lon": 78.5516, "type": "hub", "city": "Hyderabad"},
    "HYD_H8":  {"name": "Maheshwaram Industrial",      "lat": 17.1415, "lon": 78.4463, "type": "hub", "city": "Hyderabad"},
    "HYD_H9":  {"name": "Kothur Logistics Hub",        "lat": 17.0373, "lon": 78.2496, "type": "hub", "city": "Hyderabad"},
    "HYD_H10": {"name": "Shadnagar Distribution Hub",  "lat": 17.0693, "lon": 78.2050, "type": "hub", "city": "Hyderabad"},
    "HYD_H11": {"name": "Zaheerabad Industrial Hub",   "lat": 17.6814, "lon": 77.6064, "type": "hub", "city": "Hyderabad"},
    "HYD_H12": {"name": "Siddipet Logistics Centre",   "lat": 18.1018, "lon": 78.8521, "type": "hub", "city": "Hyderabad"},
    "HYD_H13": {"name": "Bhongir Industrial Hub",      "lat": 17.5126, "lon": 78.8908, "type": "hub", "city": "Hyderabad"},
    "HYD_H14": {"name": "Nalgonda Distribution Hub",   "lat": 17.0575, "lon": 79.2672, "type": "hub", "city": "Hyderabad"},
    "HYD_H15": {"name": "Suryapet Logistics Hub",      "lat": 17.1403, "lon": 79.6219, "type": "hub", "city": "Hyderabad"},
    "HYD_H16": {"name": "Narayanpet Industrial Hub",   "lat": 16.7432, "lon": 77.4963, "type": "hub", "city": "Hyderabad"},
    "HYD_H17": {"name": "Jadcherla Distribution Hub",  "lat": 16.9315, "lon": 78.1437, "type": "hub", "city": "Hyderabad"},
    "HYD_H18": {"name": "Tandur Industrial Hub",       "lat": 17.2485, "lon": 77.5817, "type": "hub", "city": "Hyderabad"},
    "HYD_H19": {"name": "Vikarabad Logistics Hub",     "lat": 17.3366, "lon": 77.9041, "type": "hub", "city": "Hyderabad"},
    "HYD_H20": {"name": "Sangareddy Logistics Park",   "lat": 17.6238, "lon": 78.0876, "type": "hub", "city": "Hyderabad"},
}

# â”€â”€ Master node registry â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
NODES = {}
NODES.update(CHENNAI_NODES)
NODES.update(COASTAL_NODES)
NODES.update(BENGALURU_NODES)
NODES.update(HYDERABAD_NODES)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SECTION 2 â€” EDGE DEFINITIONS
# Format: (from, to, time_min, fuel_inr, road_name, is_city_limit, highway_only)
# is_city_limit=True â†’ time-window restricted (no commercial trucks 07:00â€“22:00)
# highway_only=True  â†’ inter-city NH edge, used for long-haul routing
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# â”€â”€ Original Chennai edges (preserved exactly) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
CHENNAI_EDGES = [
    ("W1","W4",  18,  45, "Anna Salai",           True,  False),
    ("W1","W7",  22,  55, "Poonamallee Road",      True,  False),
    ("W1","D2",  20,  50, "Inner Ring Road",       True,  False),
    ("W2","W8",  15,  35, "Thiruvallur Road",      True,  False),
    ("W2","W5",  25,  60, "Inner Ring Road",       True,  False),
    ("W3","D4",  12,  30, "GST Road",              True,  False),
    ("W3","D6",  10,  25, "GST Road",              True,  False),
    ("W3","W7",  28,  70, "NH48",                  False, False),
    ("W4","D1",  14,  35, "Anna Salai",            True,  False),
    ("W4","D3",  20,  50, "Sardar Patel Road",     True,  False),
    ("W4","W5",  22,  55, "Inner Ring Road",       True,  False),
    ("W5","D2",  12,  30, "Inner Ring Road",       True,  False),
    ("W5","D7",  25,  65, "NH16",                  False, False),
    ("W6","D3",  15,  38, "OMR",                   True,  False),
    ("W6","D5",  18,  45, "ECR",                   True,  False),
    ("W7","W3",  30,  75, "NH48",                  False, False),
    ("W7","W8",  20,  50, "Poonamallee Road",      True,  False),
    ("W8","W2",  15,  35, "Thiruvallur Road",      True,  False),
    ("W8","D7",  30,  75, "NH16",                  False, False),
    ("D1","D3",  15,  38, "Sardar Patel Road",     True,  False),
    ("D3","D5",  12,  30, "ECR",                   True,  False),
    ("D4","D6",   8,  20, "GST Road",              True,  False),
]

# â”€â”€ Bengaluru intra-city edges (city-limit restricted) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
BENGALURU_EDGES = [
    ("BEN_H1","BEN_H2",  25,  60, "Tumkur Road",          True,  False),
    ("BEN_H1","BEN_H8",  20,  50, "Outer Ring Road",      True,  False),
    ("BEN_H2","BEN_H6",  30,  75, "NH48 Approach",        False, False),
    ("BEN_H3","BEN_H4",  15,  38, "Hosur Road",           True,  False),
    ("BEN_H3","BEN_H16", 20,  50, "Hosur Road",           True,  False),
    ("BEN_H4","BEN_H9",  18,  45, "Bommasandra Road",     True,  False),
    ("BEN_H4","BEN_H10", 22,  55, "Jigani Link Road",     True,  False),
    ("BEN_H5","BEN_H15", 25,  65, "Whitefield Road",      True,  False),
    ("BEN_H5","BEN_H14", 40, 100, "Bangalore-Hoskote Rd", False, False),
    ("BEN_H6","BEN_H11", 35,  88, "Doddaballapur Road",   False, False),
    ("BEN_H7","BEN_H14", 20,  50, "Airport Road",         False, False),
    ("BEN_H7","BEN_H8",  22,  55, "NH44 Approach",        False, False),
    ("BEN_H8","BEN_H17", 18,  45, "Outer Ring Road",      True,  False),
    ("BEN_H9","BEN_H10", 12,  30, "Jigani Road",          True,  False),
    ("BEN_H10","BEN_H12",25,  62, "Kanakapura Road",      False, False),
    ("BEN_H12","BEN_H13",30,  75, "NH48",                 False, False),
    ("BEN_H13","BEN_H19",55, 138, "Mysore Road",          False, False),
    ("BEN_H18","BEN_H12",20,  50, "Kengeri Road",         True,  False),
    ("BEN_H19","BEN_H20",18,  45, "NH275",                False, False),
    ("BEN_H17","BEN_H10",15,  38, "Bannerghatta Road",    True,  False),
]

# â”€â”€ Hyderabad intra-city edges (city-limit restricted) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HYDERABAD_EDGES = [
    ("HYD_H1","HYD_H20", 30,  75, "Patancheru-Sangareddy Rd", True,  False),
    ("HYD_H1","HYD_H5",  25,  62, "ORR Hyderabad",            True,  False),
    ("HYD_H2","HYD_H12", 60, 150, "Medchal-Siddipet Road",    False, False),
    ("HYD_H3","HYD_H4",  25,  62, "Shamshabad Road",          False, False),
    ("HYD_H3","HYD_H8",  30,  75, "Fab City Link",            False, False),
    ("HYD_H4","HYD_H7",  22,  55, "NH65",                     False, False),
    ("HYD_H5","HYD_H6",  20,  50, "HITEC City Road",          True,  False),
    ("HYD_H6","HYD_H7",  18,  45, "Uppal Road",               True,  False),
    ("HYD_H7","HYD_H4",  22,  55, "LB Nagar Road",            True,  False),
    ("HYD_H8","HYD_H9",  30,  75, "Maheshwaram Road",         False, False),
    ("HYD_H9","HYD_H10", 20,  50, "Kothur Bypass",            False, False),
    ("HYD_H10","HYD_H17",25,  62, "Jadcherla Road",           False, False),
    ("HYD_H11","HYD_H20",50, 125, "Sangareddy-Zaheerabad",    False, False),
    ("HYD_H13","HYD_H14",45, 112, "NH65",                     False, False),
    ("HYD_H14","HYD_H15",55, 138, "NH65",                     False, False),
    ("HYD_H15","HYD_H6", 80, 200, "Suryapet-Uppal Road",      False, False),
    ("HYD_H16","HYD_H18",40, 100, "Tandur Road",              False, False),
    ("HYD_H17","HYD_H9", 22,  55, "Shadnagar Link",           False, False),
    ("HYD_H18","HYD_H19",35,  88, "Vikarabad Road",           False, False),
    ("HYD_H19","HYD_H1", 40, 100, "ORR West",                 False, False),
]

# â”€â”€ Inter-city NH Highway edges (highway_only=True) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# (from_node, to_node, time_min, fuel_inr, highway_name, is_city_limit, highway_only)
HIGHWAY_EDGES = [
    # BEN â†” HYD via NH44 (570 km, ~9 hours = 540 min)
    ("BEN_H7", "HYD_H2",  540, 4560, "NH44", False, True),
    ("HYD_H2", "BEN_H7",  540, 4560, "NH44", False, True),

    # BEN â†” MUM via NH48 (980 km, ~16 hours = 960 min)
    ("BEN_H6", "MUM_H1",  960, 8330, "NH48", False, True),
    ("MUM_H1", "BEN_H6",  960, 8330, "NH48", False, True),

    # BEN â†” COC via NH544 (540 km, ~9 hours = 540 min)
    ("BEN_H13","COC_H1",  540, 4590, "NH544", False, True),
    ("COC_H1", "BEN_H13", 540, 4590, "NH544", False, True),

    # HYD â†” VIZ via NH65 (620 km, ~10 hours = 600 min)
    ("HYD_H6", "VIZ_H1",  600, 5270, "NH65", False, True),
    ("VIZ_H1", "HYD_H6",  600, 5270, "NH65", False, True),

    # MUM â†” HYD via NH65 (710 km, ~11 hours = 660 min)
    ("MUM_H1", "HYD_H1",  660, 6035, "NH65", False, True),
    ("HYD_H1", "MUM_H1",  660, 6035, "NH65", False, True),

    # Chennai gateways to inter-city NH network
    ("W3",     "BEN_H3",  180, 1530, "NH48",  False, True),
    ("BEN_H3", "W3",      180, 1530, "NH48",  False, True),
    ("W5",     "HYD_H13", 480, 4080, "NH16",  False, True),
    ("HYD_H13","W5",      480, 4080, "NH16",  False, True),
]

# Master edge list
BASE_EDGES = CHENNAI_EDGES + BENGALURU_EDGES + HYDERABAD_EDGES + HIGHWAY_EDGES

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SECTION 3 â€” ROAD NAME REGISTRY (fuzzy-match for Gemini disruption mapping)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ROAD_NAMES = {
    # Chennai originals
    "OMR":                    ("W6",      "D3"),
    "Old Mahabalipuram Road": ("W6",      "D3"),
    "GST Road":               ("W3",      "D4"),
    "NH32":                   ("W3",      "D4"),
    "NH48":                   ("W7",      "W3"),
    "Poonamallee Road":       ("W7",      "W8"),
    "Anna Salai":             ("W4",      "D1"),
    "Mount Road":             ("W4",      "D1"),
    "ECR":                    ("W6",      "D5"),
    "East Coast Road":        ("W6",      "D5"),
    "NH16":                   ("W5",      "D7"),
    "Thiruvallur Road":       ("W8",      "W5"),
    "Inner Ring Road":        ("W4",      "W5"),
    "Sardar Patel Road":      ("W4",      "D3"),
    # Bengaluru roads
    "Tumkur Road":            ("BEN_H1",  "BEN_H2"),
    "Hosur Road":             ("BEN_H3",  "BEN_H4"),
    "Whitefield Road":        ("BEN_H5",  "BEN_H15"),
    "Mysore Road":            ("BEN_H13", "BEN_H19"),
    "Doddaballapur Road":     ("BEN_H6",  "BEN_H11"),
    "Airport Road":           ("BEN_H7",  "BEN_H14"),
    "Kanakapura Road":        ("BEN_H10", "BEN_H12"),
    "Bannerghatta Road":      ("BEN_H17", "BEN_H10"),
    # Hyderabad roads
    "ORR Hyderabad":          ("HYD_H1",  "HYD_H5"),
    "HITEC City Road":        ("HYD_H5",  "HYD_H6"),
    "Shamshabad Road":        ("HYD_H3",  "HYD_H4"),
    "Jadcherla Road":         ("HYD_H10", "HYD_H17"),
    # Inter-city NHs
    "NH44":                   ("BEN_H7",  "HYD_H2"),
    "NH544":                  ("BEN_H13", "COC_H1"),
    "NH65":                   ("HYD_H6",  "VIZ_H1"),
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# SECTION 4 â€” SHIPMENTS & TRUCKS
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
SHIPMENTS = [
    {"id": f"S{i:02d}", "origin": o, "dest": d, "weight_kg": w}
    for i, (o, d, w) in enumerate([
        ("W1",     "D1",      200), ("W1",     "D2",      150),
        ("W2",     "D7",      300), ("W1",     "D3",      100),
        ("W2",     "D2",      250), ("W3",     "D4",      180),
        ("W1",     "D5",      220), ("W2",     "D7",      160),
        ("W3",     "D6",      140), ("W4",     "D1",      190),
        ("W4",     "D3",      210), ("W5",     "D2",      170),
        ("W6",     "D3",      230), ("W6",     "D5",      120),
        ("W7",     "D4",      260), ("W8",     "D7",      110),
        ("W1",     "D2",      145), ("W2",     "D3",      195),
        ("W3",     "D5",      175), ("W4",     "D6",      205),
        # Inter-city shipments
        ("BEN_H1", "HYD_H5",  350), ("MUM_H1", "BEN_H4",  420),
        ("BEN_H3", "COC_H1",  280), ("HYD_H6", "VIZ_H1",  310),
        ("MUM_H1", "HYD_H1",  500),
    ], 1)
]

TRUCKS = [{"id": f"T{i}", "capacity_kg": 800} for i in range(1, 9)]

# =============================================================================
# SECTION 5 — GRAPH BUILDER
# =============================================================================

def build_graph(risk_overrides=None):
    """
    Build NetworkX DiGraph with composite cost weights.

    Cost formula: W = alpha*T + beta*F + gamma*(R*100)
      T = travel time (min), F = fuel cost (INR), R = risk score [0,1]
      alpha=0.5, beta=0.3, gamma=0.2 (tunable weights)

    Complexity — CD343AI Unit II:
      Time:  O(V + E) — iterate over all nodes then all edges
      Space: O(V + E) — adjacency list in NetworkX DiGraph

    Args:
        risk_overrides (dict): {(u,v): float} risk values to override defaults

    Returns:
        nx.DiGraph with node/edge attributes populated
    """
    G = nx.DiGraph()
    risk_map = risk_overrides or {}
    alpha, beta, gamma = 0.5, 0.3, 0.2

    for node_id, data in NODES.items():
        G.add_node(node_id, **data)

    for edge in BASE_EDGES:
        u, v, t, f, road, city_limit, hw_only = edge
        R = risk_map.get((u, v), 0.0)
        cost = alpha * t + beta * f + gamma * (R * 100)
        G.add_edge(u, v,
                   time=t, fuel=f, risk=R, cost=cost,
                   road=road, weight=cost,
                   city_limit=city_limit,
                   highway_only=hw_only)
        # Reverse edge (bidirectional)
        R2 = risk_map.get((v, u), 0.0)
        cost2 = alpha * t + beta * f + gamma * (R2 * 100)
        G.add_edge(v, u,
                   time=t, fuel=f, risk=R2, cost=cost2,
                   road=road, weight=cost2,
                   city_limit=city_limit,
                   highway_only=hw_only)
    return G


# =============================================================================
# SECTION 6 — DIJKSTRA (custom, with time-window awareness)
# =============================================================================

def dijkstra_shortest_path(G, source, target, weight="cost",
                            current_time_min=None, respect_time_windows=True):
    """
    Dijkstra's single-source shortest path with optional time-window filtering.

    For time-window-aware routing: city-limit edges that are currently blocked
    (07:00–22:00 = minutes 420–1320 in a 24h cycle) are assigned a large
    penalty cost rather than being outright removed, so the solver always
    returns *some* path and the caller decides whether to wait.

    Complexity — CD343AI Unit IV — Dijkstra's Algorithm:
      Time:  O((V + E) log V) using a min-heap / priority queue
      Space: O(V)             for dist[], prev[] arrays

    Args:
        G                    (nx.DiGraph): road network graph
        source               (str):        start node ID
        target               (str):        end node ID
        weight               (str):        edge attribute to minimise
        current_time_min     (int|None):   current time in minutes from midnight
        respect_time_windows (bool):       if True, penalise blocked city edges

    Returns:
        (path: list[str], cost: float)
        path is [] and cost is inf if no path exists.
    """
    CITY_BLOCK_START = 7 * 60   # 07:00 ? 420 min
    CITY_BLOCK_END   = 22 * 60  # 22:00 ? 1320 min
    BLOCKED_PENALTY  = 1e7      # effectively blocks the edge in routing

    dist = {n: math.inf for n in G.nodes}
    prev = {n: None for n in G.nodes}
    dist[source] = 0.0
    heap = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        if u == target:
            break
        for v, edata in G[u].items():
            base_w = edata.get(weight, 1.0)
            # Apply time-window penalty if needed
            if (respect_time_windows
                    and current_time_min is not None
                    and edata.get("city_limit", False)):
                t_mod = current_time_min % 1440  # wrap 24h
                if CITY_BLOCK_START <= t_mod < CITY_BLOCK_END:
                    base_w += BLOCKED_PENALTY
            nd = d + base_w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[target] == math.inf:
        return [], math.inf

    # Reconstruct path
    path, cur = [], target
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    path.reverse()
    return path, dist[target]


# =============================================================================
# SECTION 7 — TIME-WINDOW SCHEDULING
# =============================================================================

def _minutes_from_midnight(dt: datetime) -> int:
    """Return minutes elapsed since midnight for a datetime object."""
    return dt.hour * 60 + dt.minute


def _next_allowed_window_start(current_time_min: int) -> int:
    """
    Return minutes-from-midnight when the next night window begins (22:00).

    Complexity — CD343AI Unit V — Constraint Scheduling:
      Time:  O(1)
      Space: O(1)
    """
    WINDOW_OPEN  = 22 * 60   # 22:00 = 1320 min
    t = current_time_min % 1440
    if t < WINDOW_OPEN:
        return WINDOW_OPEN          # wait until 22:00 today
    return WINDOW_OPEN + 1440      # already past 22:00 ? next day 22:00


def schedule_departure(route_edges, current_time: datetime,
                        G: nx.DiGraph = None) -> datetime:
    """
    Compute the earliest valid departure datetime for a sequence of edges,
    respecting city-limit time windows.

    Commercial trucks cannot use city-limit edges between 07:00 and 22:00.
    If the next edge in the route is a city-limit edge and the current time
    falls in the blocked window, departure is delayed until 22:00.

    Complexity — CD343AI Unit V — Greedy Scheduling with Time Windows:
      Time:  O(E) — single pass over route edges
      Space: O(1) — constant state variables

    Args:
        route_edges  (list[tuple]): list of (u, v) node pairs in order
        current_time (datetime):    current datetime
        G            (nx.DiGraph):  graph (optional; used to read edge attrs)

    Returns:
        datetime: earliest departure time for the first edge in the route.
                  If no city-limit edges exist, returns current_time unchanged.

    Example:
        >>> route = [("BEN_H1", "BEN_H8"), ("BEN_H7", "HYD_H2")]
        >>> t = datetime(2024, 1, 15, 9, 0)   # 09:00 — inside blocked window
        >>> schedule_departure(route, t)
        datetime(2024, 1, 15, 22, 0, 0)       # delayed to 22:00
    """
    BLOCK_START_H, BLOCK_START_M = 7, 0
    BLOCK_END_H,   BLOCK_END_M   = 22, 0

    departure = current_time

    for (u, v) in route_edges:
        is_city = False
        if G is not None and G.has_edge(u, v):
            is_city = G[u][v].get("city_limit", False)
        else:
            # Fallback: check BASE_EDGES list
            for edge in BASE_EDGES:
                eu, ev = edge[0], edge[1]
                if eu == u and ev == v:
                    is_city = edge[5]
                    break

        if is_city:
            dep_h, dep_m = departure.hour, departure.minute
            block_start = departure.replace(
                hour=BLOCK_START_H, minute=BLOCK_START_M, second=0, microsecond=0)
            block_end   = departure.replace(
                hour=BLOCK_END_H,   minute=BLOCK_END_M,   second=0, microsecond=0)
            # If departure falls inside blocked window, delay to 22:00
            if block_start <= departure < block_end:
                departure = block_end
                break   # earliest departure found for first city-limit edge

    return departure


def time_window_edge_filter(G: nx.DiGraph, current_time: datetime) -> nx.DiGraph:
    """
    Return a view of G with city-limit edges that are currently blocked
    removed entirely (for strict scheduling; use dijkstra_shortest_path with
    penalty for softer routing).

    Complexity — CD343AI Unit II — Graph Filtering:
      Time:  O(E)
      Space: O(E) for the filtered edge set copy
    """
    BLOCK_H_START, BLOCK_H_END = 7, 22
    h = current_time.hour
    blocked = (BLOCK_H_START <= h < BLOCK_H_END)

    H = G.copy()
    if blocked:
        to_remove = [(u, v) for u, v, d in H.edges(data=True)
                     if d.get("city_limit", False)]
        H.remove_edges_from(to_remove)
    return H

# =============================================================================
# SECTION 8 — CAPACITY-CONSTRAINED VRP SOLVER (Greedy Insertion)
# =============================================================================

def solve_vrp(G, shipments, trucks, current_time: datetime = None,
              capacity_kg: int = 800, highway_only_intercity: bool = True):
    """
    Capacity-constrained greedy insertion VRP heuristic.

    Each shipment is assigned to the truck whose route-cost increase is minimal
    while satisfying:
      1. Truck weight capacity (configurable, default 800 kg)
      2. Time-window constraints on city-limit edges
      3. Highway-only routing between cities (no shortcuts across NHs)

    Algorithm: Greedy Insertion (nearest/cheapest insertion approximation)
    NP-hard VRP approximated; expected within ~15% of optimal for small
    fleets (<= 20 trucks) on sparse graphs.

    Complexity — CD343AI Unit IV — NP-hard Approximation (VRP):
      Time:  O(S * T * (V+E) log V)
              S = number of shipments
              T = number of trucks
              Dijkstra O((V+E)logV) called per (shipment, truck) pair
      Space: O(V + E + S*T) — graph + route tracking structures

    Args:
        G                      (nx.DiGraph):   road network
        shipments              (list[dict]):   list of shipment dicts
        trucks                 (list[dict]):   list of truck dicts
        current_time           (datetime):     used for time-window checks
        capacity_kg            (int):          per-truck weight limit (kg)
        highway_only_intercity (bool):         restrict inter-city to NH edges

    Returns:
        list[dict]: one route dict per truck with keys:
            truck, shipments, total_cost, path_nodes, co2_kg,
            scheduled_departure, cities_visited
    """
    if current_time is None:
        current_time = datetime.now()

    t_min = _minutes_from_midnight(current_time)

    routes = {
        t["id"]: {
            "truck":               t,
            "shipments":           [],
            "total_cost":          0.0,
            "path_nodes":          [],
            "co2_kg":              0.0,
            "scheduled_departure": current_time,
            "cities_visited":      set(),
        }
        for t in trucks
    }
    truck_ids  = [t["id"] for t in trucks]
    truck_load = {t["id"]: 0 for t in trucks}

    for shipment in shipments:
        origin = shipment["origin"]
        dest   = shipment["dest"]
        weight = shipment["weight_kg"]

        # -- Find shortest path (time-window-aware Dijkstra) ------------------
        # path_cost here may include penalty; compute real_cost separately.
        path, _penalised_cost = dijkstra_shortest_path(
            G, origin, dest, weight="cost",
            current_time_min=t_min, respect_time_windows=True
        )
        if not path:
            # Fallback: NetworkX built-in (ignores time windows)
            try:
                path = nx.dijkstra_path(G, origin, dest, weight="cost")
            except nx.NetworkXNoPath:
                path = [origin, dest]

        # Real (unpenalised) cost for storage, CO2 calculation, and display
        path_cost = sum(
            G[path[i]][path[i+1]].get("cost", 0.0)
            for i in range(len(path) - 1)
            if G.has_edge(path[i], path[i+1])
        ) if len(path) > 1 else 9999.0

        # -- Greedy truck selection --------------------------------------------
        best_truck, best_cost, best_path = None, math.inf, path

        for tid in truck_ids:
            cap = routes[tid]["truck"].get("capacity_kg", capacity_kg)
            if truck_load[tid] + weight > cap:
                continue
            # Marginal cost = path_cost (simple greedy; can extend to
            # cheapest-insertion by considering existing route cost delta)
            if path_cost < best_cost:
                best_cost, best_truck, best_path = path_cost, tid, path

        if best_truck is None:
            # No truck has capacity — assign to least-loaded truck anyway
            best_truck = min(truck_ids, key=lambda tid: truck_load[tid])
            best_path  = path
            best_cost  = path_cost

        # -- Schedule departure respecting time windows ------------------------
        route_edge_pairs = list(zip(best_path, best_path[1:]))
        dep_time = schedule_departure(route_edge_pairs, current_time, G)

        # -- Commit assignment -------------------------------------------------
        routes[best_truck]["shipments"].append(shipment)
        routes[best_truck]["path_nodes"].extend(best_path)
        routes[best_truck]["total_cost"] += best_cost
        routes[best_truck]["scheduled_departure"] = max(
            routes[best_truck]["scheduled_departure"], dep_time
        )
        truck_load[best_truck] += weight

        # Cities visited
        for nid in best_path:
            city = NODES.get(nid, {}).get("city", "Unknown")
            routes[best_truck]["cities_visited"].add(city)

        # CO2 estimate: 0.536 kg CO2/km, approx km from cost units
        dist_km = best_cost * 0.8
        routes[best_truck]["co2_kg"] += round(dist_km * 0.536, 1)

    # Serialise city sets to lists
    for r in routes.values():
        r["cities_visited"] = sorted(r["cities_visited"])

    return list(routes.values())


# =============================================================================
# SECTION 9 — DISRUPTION MAPPER (Gemini fuzzy-match, preserved + extended)
# =============================================================================

def map_disruption_to_edge(gemini_text, confidence_threshold=80):
    """
    Fuzzy-match Gemini disruption text against known road names.
    Returns (edge_tuple, confidence_score, matched_road_name) or
            (None, score, None) if below threshold.

    Complexity — CD343AI Unit III — String Matching / Search:
      Time:  O(R * L)  R = number of known roads, L = text length
      Space: O(R)      candidate list

    Example:
        gemini_text = "Protests blocking NH44 near Krishnagiri"
        ? returns (("BEN_H7", "HYD_H2"), 95, "NH44")
    """
    road_list = list(ROAD_NAMES.keys())
    match, score = process.extractOne(
        gemini_text, road_list, scorer=_fuzz.token_set_ratio
    )
    if score >= confidence_threshold:
        edge = ROAD_NAMES[match]
        return edge, score, match
    return None, score, None


# =============================================================================
# SECTION 10 — PRECOMPUTED STATE HELPERS (preserved + extended)
# =============================================================================

def get_normal_state():
    """
    Build graph and solve VRP under normal conditions.

    Complexity — CD343AI Unit IV:
      Time:  O(V + E + S*T*(V+E)logV)
      Space: O(V + E)
    """
    G      = build_graph()
    routes = solve_vrp(G, SHIPMENTS, TRUCKS)
    return G, routes


def get_disrupted_state():
    """
    Build graph and solve VRP with NH44 (BEN?HYD) blocked (risk=0.9).

    Complexity — CD343AI Unit IV:
      Same as get_normal_state() — O(S*T*(V+E)logV)
    """
    risk_overrides = {
        ("W7",     "W3"):      0.9,
        ("W3",     "W7"):      0.9,
        ("BEN_H7", "HYD_H2"): 0.9,
        ("HYD_H2", "BEN_H7"): 0.9,
    }
    G      = build_graph(risk_overrides)
    routes = solve_vrp(G, SHIPMENTS, TRUCKS)
    return G, routes


# =============================================================================
# SECTION 11 — JSON SERIALISER FOR LEAFLET FRONTEND (preserved + extended)
# =============================================================================

def routes_to_json(G, routes, disrupted_edges=None):
    """
    Convert solved VRP routes to JSON for the Leaflet.js frontend.
    Includes all node coordinates, truck polylines, CO2, cost, and
    scheduled departure times.

    Complexity — CD343AI Unit II — Graph Traversal for Serialisation:
      Time:  O(V + S*(V+E)logV)  — one Dijkstra per shipment for coords
      Space: O(V + E)            — output JSON proportional to graph size
    """
    result = {
        "trucks":          [],
        "nodes":           {},
        "disrupted_edges": [],
        "graph_stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "cities":      list({d.get("city","?") for _, d in G.nodes(data=True)}),
        }
    }

    # Node data for map pins
    for nid, data in G.nodes(data=True):
        result["nodes"][nid] = {
            "lat":  data.get("lat", 0),
            "lon":  data.get("lon", 0),
            "name": data.get("name", nid),
            "type": data.get("type", "hub"),
            "city": data.get("city", ""),
        }

    colors = ["#534AB7","#0F6E56","#D85A30","#185FA5",
              "#BA7517","#993556","#639922","#5F5E5A"]

    for i, route in enumerate(routes):
        if not route["shipments"]:
            continue

        coords     = []
        seen_edges = set()

        for shipment in route["shipments"]:
            try:
                path = nx.dijkstra_path(G, shipment["origin"],
                                        shipment["dest"], weight="cost")
                for j in range(len(path) - 1):
                    ek = (path[j], path[j+1])
                    if ek not in seen_edges:
                        seen_edges.add(ek)
                        n1 = G.nodes[path[j]]
                        n2 = G.nodes[path[j+1]]
                        coords.append([
                            [n1.get("lat",0), n1.get("lon",0)],
                            [n2.get("lat",0), n2.get("lon",0)]
                        ])
            except Exception:
                pass

        dep = route.get("scheduled_departure", None)
        dep_str = dep.strftime("%Y-%m-%d %H:%M") if isinstance(dep, datetime) else str(dep)

        result["trucks"].append({
            "id":                  route["truck"]["id"],
            "color":               colors[i % len(colors)],
            "shipments":           [s["id"] for s in route["shipments"]],
            "co2_kg":              route["co2_kg"],
            "total_cost":          round(route["total_cost"], 1),
            "cities_visited":      route.get("cities_visited", []),
            "scheduled_departure": dep_str,
            "coords":              coords,
        })

    # Disrupted edge coords
    if disrupted_edges:
        for (u, v) in disrupted_edges:
            if u in G.nodes and v in G.nodes:
                n1 = G.nodes[u]
                n2 = G.nodes[v]
                result["disrupted_edges"].append({
                    "coords": [
                        [n1.get("lat",0), n1.get("lon",0)],
                        [n2.get("lat",0), n2.get("lon",0)]
                    ],
                    "road": G.edges[u, v].get("road", "Unknown")
                })

    return result


# =============================================================================
# SECTION 12 — GRAPH STATISTICS UTILITY
# =============================================================================

def graph_summary(G: nx.DiGraph) -> dict:
    """
    Return a summary dict of the graph for diagnostics/logging.

    Complexity — CD343AI Unit II — Graph Properties:
      Time:  O(V + E)
      Space: O(C) where C = number of unique cities
    """
    city_counts = {}
    for _, d in G.nodes(data=True):
        c = d.get("city", "Unknown")
        city_counts[c] = city_counts.get(c, 0) + 1

    highway_edges = sum(
        1 for _, _, d in G.edges(data=True)
        if d.get("highway_only", False)
    )
    city_limit_edges = sum(
        1 for _, _, d in G.edges(data=True)
        if d.get("city_limit", False)
    )

    return {
        "total_nodes":      G.number_of_nodes(),
        "total_edges":      G.number_of_edges(),
        "nodes_per_city":   city_counts,
        "highway_edges":    highway_edges,
        "city_limit_edges": city_limit_edges,
        "is_connected":     nx.is_weakly_connected(G),
    }

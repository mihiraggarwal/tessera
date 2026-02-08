
# Hackathon Presentation
## Motivation
- Urban Planning and policy researchers are often forced to take poor approximations of the areas they are working with. This is because although facility data and population data exist independently, there are currently no usable ways to harmonise that data to combine insights across both dimensions. 

- Tessera has been designed to address this concern. We wanted to create a platform that would give interested parties the ability to upload datasets of their choice, and use population data that we provide them, and then be able to recompute the approximate populations of the voronoi cells for each of the facilities, which brings to light a host of new insights. 

- We do this by taking underlying city and district level population data, and recomputing the population of the cell as a weighted mean of all the districts that are either subsets or overlapping with that cell. We use this as a proxy for the serviceable region for that facility. 

[Show them the basic flow]

## Basic Flow
- Here, you begin either by loading a dataset we already have made available (from OSM), or by dragging and dropping a dataset of your own. We load the facilities onto the map by latitude and longitude. Then, we hit the compute voronoi button, and this produces a voronoi plot for the entire country, with the facilities as voronoi centres. Then, if you hover over any of the cells, it will give you the associated metadata for that cell, and also tell you the newly computed population, and which districts it has taken these numbers from.

- Additionally, if you want to only look at a particular state, it will ignore all other points and focus your analysis do the state you have picked. You can also add and delete facilities as you want, and the voronoi plot will be recomputed.

## Procedurally Generated Insights
### Facility Analytics & Strategic Insights
- Searches for largest coverage gap, and gives you the best location to place a new facility to cover that gap. Also tells you which facility is serving the most people, top 5 by population and by density. 
### Area Analysis
- We have a composite score, that is computed as a function of the distance of the point from a variety of critical faciltiies, and also a score that is computed based on proximity to good-to-have facilities. This heatmap tells us about what the best places to live are, and which areas are underserved.

## Road Networks
We also recongised that euclidian distance may not be the best proxy for something like facility proximity.

### Distance Mode

We support multiple distance calculation methods that fundamentally change how service areas are computed:

- **Euclidean Mode**: Traditional straight-line distance Voronoi diagrams. Fast computation, ideal for initial exploration and scenarios where actual travel paths don't significantly differ from straight lines (e.g., rural areas with grid-like roads).

- **Road Network Modes** (requires OSRM routing service):
  - **Road (Grid)**: Uses a grid-sampling approach where we generate a uniform grid of sample points across the region, query the road network for actual driving distances from each point to nearby facilities, then interpolate these assignments into service area polygons. This captures road network topology and one-way streets accurately.
  
  - **Road (Edge)**: Faster approximation that samples along Voronoi cell edges rather than a full grid, reducing computation time while maintaining reasonable accuracy for road-distance-based boundaries.
  
  - **Road (Weighted)**: Hybrid approach that weights facility assignments by both distance and population density, useful for capacity-constrained planning.

The system includes adaptive candidate filtering using k-nearest neighbors to make road network queries efficient—we don't query routing for all facilities, just the k most likely candidates based on Euclidean distance, with automatic expansion if road distortion is high (e.g., mountains, rivers blocking direct routes).

**Key Insight**: Road-based Voronoi can differ dramatically from Euclidean in areas with geographic barriers (rivers, mountains), one-way street systems, or sparse road networks. A hospital 2km away as the crow flies might be 15km away by road—our system reveals these real-world access patterns.

### Cell Select Route Analysis (Only Gujarat for now)

Once you've computed a Voronoi diagram, you can double-click anywhere on the map to trigger detailed route analysis for that location:

- **Nearest Facility by Road**: Instead of just showing which Voronoi cell you're in, the system queries the actual road network to find the facility with the shortest driving distance and time to your selected point.

- **Multi-Facility Comparison**: For each clicked location, we show routing metrics to nearby facilities including:
  - Actual driving distance (km) and estimated travel time (minutes)
  - Route distortion ratio (road distance ÷ Euclidean distance) to identify areas where geography creates access barriers
  - Connectivity status (whether a road route exists at all)

- **Coverage Confidence**: The system computes a confidence score based on how much closer the nearest facility is compared to the second-nearest. Low confidence indicates boundary areas where service territory is ambiguous—useful for identifying where to place new facilities.

**Current Limitation**: This feature requires pre-processed OSRM routing data. We currently have complete road network data for Gujarat state. Expanding to other states requires downloading OSM extracts and building OSRM graph files, which we're actively working on. The technical infrastructure is fully generalized—it's purely a data provisioning challenge.

**Use Case**: A policymaker can click on a remote village and immediately see: "Nearest hospital is 23km away, 35-minute drive—but there's a hospital 8km away as the crow flies across an unbridged river." This reveals infrastructure priorities that Euclidean analysis would miss entirely.

## AI Features
A concern we had was that a lot of the target audience we had in mind were people we did not want to assume knowledge of voronoi plots, and DCEL's, we wanted to provide some kind of a bridge between what was being compuuted and what the researchers would want to extract from it. Consequently, we wrote a chatbot to assist users in LLM-powered data exploration.
### Data Exploration
- We have a Chatbot (currently support Google and OpenAI) which can be used for any kind of data exploration: we have given the model to iterate over user queries and write functions for any query they would want to make. This means that the choices of function are not hardcoded, but are instead written by the LLM itself, because we did not want to be the limiting factors in researchers exploration.
- The function can be shown for verifiability purposes, should the user want to double check a query
- LLM also has access to all the procedurally generated insights via tool calls, so all the analysis from across the app is accessible via the chatbot
### Data Augmentation
- One more issue is that we did not want users to have to deal with data augmentation to bring the data into the requisite format. This would have added a layer of friction for the users. So, you can drag and drop yourr facility csv into the chatbot frame, and it will either edit the column names and general formatting to make the data compatible with our code, or will tell you if the data is missing the columns you need.

- Keys are stored locally, do not go anywhere

## Technical Innovation Highlights

- **Hybrid Distance Computation**: Candidate filtering with DCEL-based k-NN (O(log n) per query) followed by precise road network routing only for likely candidates—makes road-based Voronoi feasible for national-scale datasets.

- **Population Weighted Cells**: Novel approach to population estimation that handles overlapping district boundaries without double-counting. Each Voronoi cell's population is computed as a weighted sum of intersecting districts, proportional to the overlap area.

- **LLM-Powered Python REPL**: Instead of rigid pre-defined analytics functions, our chatbot writes and executes arbitrary Python code against the spatial index. Researchers can ask any question—the LLM decides what code to write. This eliminates us as the bottleneck for data exploration capabilities.

- **District-Level Filtering**: New capability (just implemented!) to restrict analysis to specific cities/districts, dramatically reducing computation time for focused regional planning without losing accuracy.


# Hackathon Presentation
## Motivation
- Urban Planning and policy researchers are often forced to take poor approximations of the areas they are working with. This is because although facility data and population data exist independently, there are currently no usable ways to harmonise that data to combine insights across both dimensions. 

- Tessera has been designed to address this concern. We wanted to create a platform that would give interested parties the ability to upload datasets of their choice, and use population data that we provide them, and then be able to recompute the approximate populations of the voronoi cells for each of the facilities, which brings to light a host of new insights. 

- We do this by taking underlying city and district level populationd data, and recomputing the population of the cell as a weighted mean of all the districts that are either subsets or overlapping with that cell. We use this as a proxy for the serviceable region for that facility. 

[Show them the basic flow]

## Basic Flow
- Here, you begin either by loading a dataset we already have made available (from OSM), or by dragging and dropping a dataset of your own. We load the facilities onto the map by latitude and longitude. Them, we hit the compute voronoi button, and this produces a voronoi plot for the entire country, with the facilities as voronoi centres. Then, if you hover over any of the cells, it will give you the associated metadata for that cell, and also tell you the newly computed population, and which districts it has taken these numbers from.

- Additionally, if you want to only look at a particular state, it will ignore all other points and focus your analysis do the state you have picked. You can also add and delete facilities as you want, and the voronoi plot will be recomputed.

## Procedurally Generated Insights
### Facility Analytics & Strategic Insights
- 
### Area Analysis

## Road Networks
### Distance Mode
### Cell Select Route Analysis (Only Gujarat for now)
have plans to expand blah blah blah

## AI Features
A concern we had was that a lot of the target audience we had in mind were people we did not want to assume knowledge of voronoi plots, and DCEL's, we wanted to provide some kind of a bridge between what was being compuuted and what the researchers would want to extract from it. Consequently, we wrote a chatbot to assist users in LLM-powered data exploration.
### Data Exploration
- We have a Chatbot (currently support Google and OpenAI) which can be used for any kind of data exploration: we have given the model to iterate over user queries and write functions for any query they would want to make. This means that the choices of function are not hardcoded, but are instead written by the LLM itself, because we did not want to be the limiting factors in researchers exploration.
- Thee function can be shown for verifiability purposes, should the user want to double check a query
- LLM also has access to all the procedurally generated insights via tool calls, so all the analysis from across the app is accessible via the chatbo
### Data Augmentation
- One more issue is that we did not want users to have to deal with data augmentation to bring the data into the requisite format. This would have added a layer of friction for the users. So, you can drag and drop yourr facility csv into the chatbot frame, and it will either edit the column names and general formatting to make the data compatible with our code, or will tell you if the data is missing the columns you need.

- Keys are stored locally, do not go anywhere

## Map Features

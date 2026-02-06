# Tessera LLM Reference

Complete technical reference for understanding and extending the Tessera codebase.

## Project Overview

Tessera is a Voronoi-based population mapping and facility planning platform designed for policymakers and urban planners in India. It helps visualize and optimize facility placement using spatial analysis.

---

## Architecture

```
tessera/
  backend/             # Python FastAPI server
    app/
      main.py          # App entry point, CORS, router registration
      routers/         # API endpoint definitions
      services/        # Business logic and algorithms
    requirements.txt   # Python dependencies
    
  frontend/            # Next.js 16 React application
    src/
      app/             # Next.js app router pages
      components/      # React components
      lib/             # Utilities and API client
    package.json       # Node dependencies
```

---

## Backend (FastAPI)

### Entry Point
**File:** `backend/app/main.py`

- FastAPI app with CORS for localhost:3000, localhost:3001, and Vercel domains
- API version: 0.2.0

### Routers

| Router | Prefix | File | Purpose |
|--------|--------|------|---------|
| voronoi | `/api/voronoi` | `routers/voronoi.py` | Voronoi diagram computation |
| upload | `/api/upload` | `routers/upload.py` | CSV/file upload handling |
| boundaries | `/api/boundaries` | `routers/boundaries.py` | India/state GeoJSON boundaries |
| population | `/api/population` | `routers/population.py` | Population data endpoints |
| dcel | `/api/dcel` | `routers/dcel.py` | Spatial index queries |
| chat | `/api/chat` | `routers/chat.py` | AI chatbot endpoints |

### API Endpoints

#### Voronoi (`/api/voronoi`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/compute` | Compute Voronoi diagram from facilities |
| GET | `/sample` | Get sample diagram with Indian cities |
| POST | `/insights` | Get facility analytics (coverage, gaps) |
| POST | `/find-nearest` | Find nearest facility to a point |

#### DCEL Spatial Queries (`/api/dcel`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/query-point` | Find facility serving a lat/lng location |
| POST | `/range-query` | Find facilities in bounding box |
| POST | `/top-by-population` | Get top N facilities by population |
| GET | `/adjacent/{facility_id}` | Get neighboring facilities |
| GET | `/summary` | Get DCEL index summary |

#### Chat AI (`/api/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/new` | Create new chat session |
| POST | `/message` | Send message (requires API key) |
| GET | `/history/{session_id}` | Get conversation history |
| DELETE | `/clear/{session_id}` | Clear conversation |

#### Upload (`/api/upload`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/csv` | Upload CSV file with facilities |
| GET | `/sample-data` | Get sample facility data |
| GET | `/available-files` | List uploaded files |
| GET | `/load-file/{filename}` | Load a saved file |

#### Boundaries (`/api/boundaries`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/india` | India country boundary GeoJSON |
| GET | `/state` | All state boundaries |
| GET | `/district` | All district boundaries |
| GET | `/states/list` | List of state names |
| GET | `/states/{name}` | Single state boundary |

### Services

| Service | File | Purpose |
|---------|------|---------|
| VoronoiEngine | `services/voronoi_engine.py` | Voronoi computation with scipy, clipping with Shapely |
| DCEL | `services/dcel.py` | Spatial index using R-tree (STRtree) |
| ChatService | `services/chat_service.py` | LangChain agent with OpenAI GPT-4 |
| PopulationService | `services/population_calc.py` | Population weighted calculations |
| AnalyticsService | `services/analytics_service.py` | Coverage analysis, enclosing circles |

### DCEL Service (`services/dcel.py`)

Data structure for efficient spatial queries on Voronoi diagrams:

- `DCELFace`: Represents a Voronoi cell with facility info and geometry
- `DCEL`: Container with R-tree spatial index
- `build_from_voronoi()`: Builds index from GeoJSON
- `point_query()`: O(log n) point-in-polygon lookup
- `range_query()`: Bounding box intersection query
- `get_current_dcel()`: Global accessor for current index

### Chat Service (`services/chat_service.py`)

LangChain integration for natural language queries with multi-provider support:

- **Providers**: OpenAI GPT-4 and Google Gemini 2.0 Flash
- Uses function calling for tool execution
- Tools wrap DCEL endpoints (point query, range query, etc.)
- In-memory conversation storage by session ID
- System prompt tailored for policymakers

**Supported Models:**
- OpenAI: `gpt-4`
- Google: `gemini-2.5-flash`

**Tools available to LLM:**
- `query_point_facility`: Find facility at lat/lng
- `get_top_facilities_by_population`: Rank by population
- `get_facility_neighbors`: Adjacent facilities
- `get_dcel_summary`: Index statistics
- `find_facilities_in_area`: Range query

---

## Frontend (Next.js)

### Structure

```
src/
  app/
    page.tsx      # Main application page
    layout.tsx    # Root layout with fonts
    globals.css   # Tailwind + CSS variables
    
  components/
    Chat/
      ChatPanel.tsx   # Chat UI with messages
      ChatButton.tsx  # Floating trigger button
      index.ts        # Exports
    FileUpload/
      index.tsx       # CSV upload component
    Map/
      index.tsx       # Leaflet map wrapper
      
  lib/
    api.ts        # Axios client + all API functions
    export.ts     # PNG/GeoJSON export utilities
```

### Key Components

#### `page.tsx`
Main page with:
- 3-column grid layout (sidebar, map, legend)
- Facility upload and management
- Voronoi computation controls
- Map visualization with Leaflet
- Analytics/insights panel
- ChatButton integration

#### `ChatPanel.tsx`
Chat interface with:
- Message list with user/assistant styling
- OpenAI API key input (stored in localStorage)
- Session management (new chat, history)
- Loading states and error handling
- Suggestion prompts for first-time users

#### `ChatButton.tsx`
Floating action button that toggles ChatPanel visibility.

### API Client (`lib/api.ts`)

Axios-based client with typed interfaces:

```typescript
voronoiApi.compute(request)      // Compute Voronoi
voronoiApi.getInsights(request)  // Get analytics
uploadApi.uploadCSV(file)        // Upload facilities
boundariesApi.getStatesList()    // Get states
chatApi.sendMessage(request)     // Send to AI
chatApi.newSession()             // Start chat
```

### Styling
- Tailwind CSS 4 with custom configuration
- CSS variables for theming (light/dark support)
- No gradients or generic purple (per user rules)

---

## Data Flow

### Voronoi Computation
1. User uploads CSV with facility data
2. Frontend calls `POST /api/voronoi/compute`
3. Backend computes Voronoi with scipy
4. Clips to India/state boundary with Shapely
5. Builds DCEL spatial index
6. Returns GeoJSON with population data
7. Frontend renders on Leaflet map

### Chat Query
1. User types question in ChatPanel
2. Frontend calls `POST /api/chat/message` with API key
3. Backend creates LangChain agent with tools
4. LLM decides which tools to call
5. Tools call optimized service functions directly (prevents HTTP deadlocks)
6. LLM synthesizes response
7. Response displayed in chat

---

## Environment

### Backend
- Python 3.11+
- FastAPI, uvicorn
- scipy, shapely, geopandas, pyproj
- langchain, langchain-openai, openai

### Frontend
- Node.js 18+
- Next.js 16, React 19
- Tailwind CSS 4
- Leaflet, axios, @turf/turf
- react-markdown, remark-gfm (for chat rich text)

### Running Locally
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## Key Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/main.py` | 51 | App entry, routes |
| `backend/app/services/voronoi_engine.py` | 421 | Voronoi math |
| `backend/app/services/dcel.py` | 388 | Spatial index |
| `backend/app/services/chat_service.py` | 235 | LangChain agent |
| `backend/app/routers/voronoi.py` | 214 | Voronoi endpoints |
| `backend/app/routers/chat.py` | 106 | Chat endpoints |
| `frontend/src/app/page.tsx` | 773 | Main page |
| `frontend/src/components/Chat/ChatPanel.tsx` | 298 | Chat UI |
| `frontend/src/lib/api.ts` | 269 | API client |

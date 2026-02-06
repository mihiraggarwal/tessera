# Changelog

All notable changes to Tessera will be documented in this file.

## [0.2.0] - 2026-02-06

### Added

**Phase 1: DCEL Spatial Index**
- New `dcel.py` service with R-tree spatial indexing for efficient point-in-polygon queries
- `DCELFace` data structure for storing Voronoi cells with metadata
- `/api/dcel/query-point` - Find which facility serves a location
- `/api/dcel/range-query` - Find facilities in a bounding box
- `/api/dcel/top-by-population` - Get facilities ranked by population served
- `/api/dcel/adjacent/{facility_id}` - Find neighboring facilities
- `/api/dcel/summary` - Get DCEL structure summary
- `compute_voronoi_with_dcel()` method in VoronoiEngine for automatic DCEL building

**Phase 2: AI Chatbot Core**
- LangChain integration with multi-provider support: OpenAI (GPT-4) and Google Gemini (2.5 Flash)
- `chat_service.py` refactored to call DCEL service functions directly, eliminating self-referential HTTP deadlocks
- Tool payload optimization (pruning large geometry/property fields) to prevent LLM timeouts
- Markdown rendering support in Chat UI using `react-markdown` and `remark-gfm`
- Comprehensive unit test suite for DCEL endpoints (`backend/tests/test_dcel_full.py`)
- /api/chat/message - Send message to AI assistant
- /api/chat/history/{session_id} - Get conversation history
- /api/chat/clear/{session_id} - Clear conversation
- /api/chat/new} - Start new conversation session
- In-memory conversation storage with session management
- System prompt optimized for policymakers and urban planners

### Changed
- Voronoi compute endpoint now automatically builds DCEL for spatial queries
- API version bumped to 0.2.0
- Added localhost:3001 to CORS origins

### Dependencies Added
- `langchain>=0.3.0`
- `langchain-openai>=0.2.0`
- `openai>=1.50.0`
- `httpx>=0.27.0`

## [0.1.0] - Initial Release

### Added
- Voronoi diagram computation with India boundary clipping
- State-level filtering for Voronoi diagrams
- Population weighted calculations
- Facility insights (coverage radius, empty circles, overburdened facilities)
- CSV/Excel data upload
- GeoJSON boundary endpoints

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
- `/api/chat/message` - Send message to AI assistant
- `/api/chat/history/{session_id}` - Get conversation history
- `/api/chat/clear/{session_id}` - Clear conversation
- `/api/chat/new` - Start new conversation session
- In-memory conversation storage with session management
- System prompt optimized for policymakers and urban planners

**Phase 3: Python REPL Architecture**

- Complete refactor of chat service to **Python REPL execution model**
- New `python_executor.py` service for sandboxed Python code execution with pattern blocking
- New `helper_functions.py` service with DCEL query helpers injected into execution environment
- Replaced 10+ specialized tools with **4 core tools**:
  - `execute_python` - Execute arbitrary Python against DCEL
  - `get_available_values` - Discover unique field values
  - `fuzzy_search` - Find matches for misspelled queries
  - `inspect_sample` - View sample facilities
- Helper functions for safe data access:
  - `safe_filter_by_state()` - Fuzzy-match state filtering
  - `safe_filter_by_district()` - District filtering with optional state
  - `safe_get_property()` - Null-safe property access with population_breakdown extraction
  - `get_stats()` - Aggregate statistics computation
  - `get_top_n()` - Sorting and limiting facilities
- Fixed state/district property access to extract from `population_breakdown` array
- System prompt rewritten to teach LLM Python code patterns instead of tool usage
- Multi-model Gemini support: `gemini-1.5-pro`, `gemini-2.5-flash`, `gemini-3-pro-preview`

### Changed

- Voronoi compute endpoint now automatically builds DCEL for spatial queries
- Insights endpoint (`/api/voronoi/insights`) updated to use `compute_voronoi_with_dcel()` for DCEL persistence
- Chat service max iterations increased to 5 for complex multi-step queries
- API version bumped to 0.2.0
- Added localhost:3001 to CORS origins

### Fixed

- **Security**: Mitigated LangChain CVE-2025-65106 by eliminating f-strings in prompt templates
- **Security**: Removed RestrictedPython dependency in favor of simpler pattern-based blocking
- DCEL availability: Ensured DCEL is stored globally after Voronoi computation
- State/district extraction: Updated all helpers and tools to extract from nested `population_breakdown`
- Agent iteration limits: Removed unsupported `early_stopping_method` parameter

### Dependencies Added

- `langchain>=0.3.0`
- `langchain-openai>=0.2.0`
- `langchain-google-genai>=2.0.0`
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

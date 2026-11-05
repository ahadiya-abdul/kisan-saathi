# Kisan Saathi (Fieldwise) — ICAR Biological Control Advisory Platform

An evidence-grounded, multilingual agricultural decision-support web application designed for Indian smallholder farmers. The system delivers personalized, scientifically verified biological crop protection advice based on official Indian Council of Agricultural Research (ICAR) guidelines, complete with itemized budget planning, economic threshold levels (ETL), computer vision triage, and a source-provenance-aware knowledge graph.

---

## Table of Contents
1. [Overview & Core Philosophy](#overview--core-philosophy)
2. [What Is in the Website](#what-is-in-the-website)
   - [Multilingual Interface](#1-multilingual-interface-6-languages)
   - [Farmer Authentication & Profile Management](#2-farmer-authentication--profile-management)
   - [Step 1: Farmer Context & Crop Profiling](#3-step-1-farmer-context--crop-profiling)
   - [Step 2: AI Photo Diagnostic Triage](#4-step-2-ai-photo-diagnostic-triage)
   - [Step 3: Section B Decision Cards](#5-step-3-section-b-decision-cards)
   - [Interactive AI Advisory Chatbot](#6-interactive-ai-advisory-chatbot)
   - [Evidence Corpus & Knowledge Graph Explorer](#7-evidence-corpus--knowledge-graph-explorer)
3. [Verified ICAR Knowledge Base](#verified-icar-knowledge-base)
4. [System Architecture & Tech Stack](#system-architecture--tech-stack)
5. [Directory Structure](#directory-structure)
6. [Quickstart & Installation](#quickstart--installation)
7. [API Endpoints](#api-endpoints)
8. [Automated Verification & Tests](#automated-verification--tests)

---

## Overview & Core Philosophy

Conventional agricultural chatbots often hallucinate unverified chemical dosages or generic advice. **Kisan Saathi** enforces an **evidence-first, zero-hallucination policy**:
- **Strict Evidence Grounding**: The system only recommends biological interventions explicitly documented in verified ICAR publications.
- **Transparent Provenance**: Every advisory response displays clickable citations, source IDs, explanation logic (*Why*), and uncertainty limits.
- **Fail-Safe Resilience**: When external LLM APIs experience high load or connection latency, an agronomic fallback engine delivers verified ICAR advice with exact benchmarks in under 0.25 seconds.
- **Organic & Safe**: Focuses exclusively on non-toxic biological controls (parasitoids, predators, entomopathogenic fungi, viruses, and botanicals) that preserve soil biology and leave zero chemical residues.

---

## What Is in the Website

### 1. Multilingual Interface (6 Languages)
Accessible across the top navigation bar with instant script switching without page reloads:
- **English** (`en`)
- **हिंदी (Hindi)** (`hi`)
- **ಕನ್ನಡ (Kannada)** (`kn`)
- **தமிழ் (Tamil)** (`ta`)
- **తెలుగు (Telugu)** (`te`)
- **മലയാളം (Malayalam)** (`ml`)

All UI buttons, tooltips, placeholders, and advisory text are localized natively.

---

### 2. Farmer Authentication & Profile Management
- **Registration & Login**: Secure sign-in via Email or 10-digit Mobile Phone Number + PIN/Password.
- **Security**: Passwords hashed with PBKDF2-HMAC-SHA256 (600,000 rounds).
- **Session Handling**: Server-side session tokens stored in secure `HttpOnly`, `SameSite=Lax` cookies (no sensitive credentials exposed in localStorage).
- **Persistent Farm State**: Farmer profile (crop, location, acreage, soil, budget) persists across sessions in a local SQLite database (`data/fieldwise.db`).

---

### 3. Step 1: Farmer Context & Crop Profiling
A dedicated form that establishes canonical context for all AI decisions:
- **Crop Selection**: Cotton, Maize, Sorghum, Pigeonpea (Red Gram), Tomato, Chickpea, Chilli, Rice, etc.
- **Growth Stage**: Seedling, Squaring, Flowering, Boll/Pod Formation, Maturity/Harvest.
- **Acreage & Soil**: Farm size in acres/hectares, and soil type (Black Soil, Red Sandy Loam, Clay Loam, Alluvial).
- **Location & GPS**: Village, Taluk/District, State with automated browser geolocation.
- **Microclimate / Live Weather**: Ambient temperature (°C), relative humidity (%), and rainfall probability.
- **Budget**: Farmer's planned investment limit in Indian Rupees (₹).

---

### 4. Step 2: AI Photo Diagnostic Triage
A computer vision triage pipeline for instant field photo assessment:
- **Upload / Camera Capture**: Direct drag-and-drop or smartphone camera image upload.
- **Dual Assessment Modes**:
  - **Plant Symptom Triage**: Inspects leaves, stems, bolls, and flowers for chewing damage, entry boreholes, discoloration, or wilt symptoms. Provides a cautious *candidate issue* without making definitive laboratory claims.
  - **Soil Surface Observation**: Evaluates surface color, aggregate texture, crusting, cracking, and moisture indicators, guiding farmers on when a chemical soil lab test is necessary.

---

### 5. Step 3: Section B Decision Cards
Six modular, evidence-grounded decision cards delivering structured ICAR guidance:

#### Card 1: Biological Crop Protection Plan (`#runPlan`)
- Generates a chronological 4-stage integrated pest management calendar (Sowing, Vegetative, Flowering/Squaring, and Maturity).
- Recommends specific bio-agents (*Trichogramma* parasitoids, *Chrysoperla* predators, neem formulations) synchronized to the crop's development timeline.

#### Card 2: Treatment & Tank-Mix Compatibility (`#runCompat`)
- Verifies biological compatibility before tank mixing.
- Flags critical hazards (e.g., never tank-mix entomopathogenic fungi like *Beauveria bassiana* with chemical fungicides; enforces the mandatory 7-day safety interval).

#### Card 3: Weather-Responsive Risk Advisory
- Combines live temperature, humidity, and rainfall forecasts to adjust application timing.
- Advises against spraying before heavy rains to prevent formulation wash-off, and advises applying microbial biopesticides in high-humidity late afternoon hours to protect live spores from UV degradation.

#### Card 4: Local Bio-Input Availability & KVK Locator (`#runSupp`)
- Directs farmers to verified district Krishi Vigyan Kendras (KVK), State Agricultural Universities (SAUs), and registered ICAR bio-centers.
- Prevents black-market or counterfeit bio-agent purchases.

#### Card 5: Itemized ICAR Biological Budget Plan (`#runBudget`)
- Computes an **actionable, itemized cost breakdown** scaled precisely to field acreage:
  1. *Trichogramma* parasitoid cards (@ ₹70–90/card; 2 cards/acre).
  2. Pheromone delta/funnel traps + lures (@ ₹60–80/trap; 5–8 traps/acre).
  3. Commercial microbial bio-sprays (*Shatpada Larvicide*, *Mycoguard Bb-L*, *Bt*, *Beauveria* @ ₹350–450/L).
  4. Botanical repellents (5% Neem Seed Kernel Extract / Azadirachtin 10,000 ppm).
- Displays total estimated investment in ₹, remaining budget surplus, and estimated savings compared to chemical insecticide rounds.

#### Card 6: Authoritative Pest Risk Check & Outbreak Warning (`#runRisk`)
- Evaluates field risk level (**HIGH**, **MODERATE**, or **LOW**).
- Defines authoritative ICAR **Economic Threshold Levels (ETL)**:
  - *Cotton Pink Bollworm*: 8 adult moths/trap/night for 3 consecutive nights OR 10% damaged green bolls / rosette flowers.
  - *American Bollworm*: 1 larva/plant OR 5–8 moths/trap/night OR 5–10% flared squares.
  - *Maize Fall Armyworm*: 5–10% seedling whorl damage or 3 moths/trap/day.
- Outlines exact 'W'-pattern field scouting instructions and immediate biological release triggers.

---

### 6. Interactive AI Advisory Chatbot
- **Conversational Assistant**: Farmers can ask open-ended questions in any supported language (e.g. *"How many Trichocards should I buy for 3 acres of cotton?"* or *"कपास में गुलाबी सुंडी के लिए क्या करें?"*).
- **Cited Sources**: Displays interactive badge links to verified ICAR reference publications.
- **Explanation Panel**: Explains the biological mechanism of action (*Why*) and specific operational limits (*Uncertainty*).

---

### 7. Evidence Corpus & Knowledge Graph Explorer
- **Source Register** (`/api/sources`): Complete registry of all active ICAR documents, verification flags, and source URLs.
- **Knowledge Graph Viewer**: Explores curated biological relationships (e.g., `Trichogramma chilonis` —*parasitizes*→ `Pink Bollworm Eggs`; `Black Soil` —*supports*→ `Cotton`).

---

## Verified ICAR Knowledge Base

The RAG index comprises authoritative ICAR documents in `data/documents/`:
1. **ICAR Technologies: Biopesticides for Eco-Friendly Pest Management** (`icar_biopesticides_technologies_compendium.txt`):
   - Detailed specifications for 31 commercialized microbial and botanical technologies developed by ICAR-NBAIR, ICAR-CICR, and ICAR-IARI (*Shatpada Larvicide*, *Shatpada Armour*, *Shatpada Terminator*, *Mycoguard Bb-L*, *Bio-Pulse*, *ARKA Krishi Vriddhi*, *ARKA Krishi Veera*).
2. **ICAR-CICR Cotton Bollworm & Sucking Pest Guidelines** (`icar_cotton_bollworm_and_sucking_pests.txt`):
   - Comprehensive IPM protocols for Pink Bollworm, American Bollworm, Whiteflies, Jassids, and Thrips with official ETL benchmarks and scouting matrices.
3. **ICAR-NBAIR Maize Fall Armyworm IPM** (`icar_maize_fall_armyworm_ipm.txt`):
   - Bio-control releases and whorl application methods.
4. **ICAR Pigeonpea Pod Borer & Wilt IPM** (`icar_pigeonpea_pod_borer_and_wilt_ipm.txt`).
5. **ICAR Sorghum Stem Borer & Shoot Fly Guidelines** (`icar_sorghum_stem_borer_and_shoot_fly.txt`).
6. **ICAR General Soil & Plant Health Guide** (`icar_general_soil_and_plant_health_guide.txt`).

---

## System Architecture & Tech Stack

```
   ┌────────────────────────────────────────────────────────┐
   │                   Browser / Frontend                   │
   │  dashboard-v2.html · app-v2.js · v2.css · i18n/*.json  │
   └───────────────────────────┬────────────────────────────┘
                               │ HTTP / JSON / SSE
                               ▼
   ┌────────────────────────────────────────────────────────┐
   │                  FastAPI Backend Server                │
   │           (backend/main.py · port 8000)                │
   ├───────────────────────────┬────────────────────────────┤
   │  Authentication & AuthZ   │  SQLite Database Engine    │
   │  PBKDF2 / Session Cookies │  (data/fieldwise.db)       │
   ├───────────────────────────┼────────────────────────────┤
   │   Hybrid Retrieval (RAG)  │  Knowledge Graph Engine    │
   │   TF-IDF + Context Filter │  (backend/services/kg.py)  │
   └───────────────────────────┬────────────────────────────┘
                               │
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│   Google Gemini API     │           │ Agronomic Fallback &    │
│   (gemini-3.8-flash)    │──(503/───▶│ Circuit Breaker Engine  │
│   8,000 ms Timeout      │   Timeout)│ (0.24s Verified ICAR)   │
└─────────────────────────┘           └─────────────────────────┘
```

- **Backend**: Python 3.11+, FastAPI, Uvicorn, SQLite3, Google GenAI SDK.
- **Frontend**: Vanilla ES6+ JavaScript, CSS3 Grid/Flexbox, Native Web APIs (Geolocation, Camera, AbortController).
- **Resilience**: 8-second remote call timeout with automatic circuit breaker failover.

---

## Directory Structure

```text
biocontrolchatbot/
├── backend/
│   ├── main.py                  # FastAPI server, routing & decision endpoints
│   └── services/
│       ├── gemini.py            # Gemini LLM client, circuit breaker & ICAR fallback
│       ├── knowledge_graph.py   # Curated biological entity & relation search
│       └── local_corpus.py      # TF-IDF lexical indexer & context-ranked RAG
├── data/
│   ├── documents/               # Official ICAR documents & sources.json register
│   └── fieldwise.db             # SQLite database (users, profiles, chat history)
├── frontend/
│   └── dashboard-v2.html        # Primary responsive single-page web app
├── static/
│   ├── app-v2.js                # Core frontend client, state manager & API callers
│   ├── v2.css                   # Responsive styles, mobile-first design
│   └── i18n/                    # 6 native language translation JSON catalogs
├── tests/                       # Pytest test suite for i18n catalogs and APIs
├── requirements.txt             # Python package dependencies
├── run.py                       # Main application launcher
└── README.md                    # Project documentation
```

---

## Quickstart & Installation

### 1. Prerequisites
- Python 3.11 or higher
- PowerShell (Windows) or Bash (macOS/Linux)

### 2. Setup Virtual Environment
```powershell
# Windows
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Variables
Create or edit `.env` in the root folder:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.8-flash
GEMINI_ENABLED=true
FIELDWISE_SECRET=your_random_secret_key_here
```

### 4. Run the Server
```powershell
python run.py
```
Open your browser at **`http://127.0.0.1:8000/`**.

---

## API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Web application dashboard |
| `GET` | `/#/advice` | Direct anchor to Field Advice & Decision Hub |
| `POST` | `/api/auth/register` | Register new farmer account |
| `POST` | `/api/auth/login` | Login and obtain session cookie |
| `GET` | `/api/auth/me` | Fetch authenticated user information |
| `PUT` | `/api/farmer/context` | Save farmer crop, acreage, and location context |
| `POST` | `/api/image-analyze` | Computer vision triage for crop or soil photo |
| `POST` | `/api/chat` | Main conversational RAG advisor endpoint |
| `POST` | `/api/budget-optimize` | Calculate itemized ICAR biological budget plan |
| `POST` | `/api/outbreak-warning` | Assess pest risk level and official ETL thresholds |
| `POST` | `/api/pest-planner` | Generate 4-stage biological crop protection plan |
| `POST` | `/api/treatment-compatibility`| Verify biological tank-mix compatibility |
| `GET` | `/api/sources` | Return list of verified ICAR evidence documents |
| `GET` | `/health` | Server health check probe |
| `GET` | `/docs` | Interactive Swagger API documentation |

---

## Automated Verification & Tests

To execute the test suite and verify language catalogs, placeholders, and scripts:
```powershell
python -m pytest tests/test_i18n_catalogs.py
```
*Expected: 4 passed in ~0.15s (100% key coverage across all 6 languages).*

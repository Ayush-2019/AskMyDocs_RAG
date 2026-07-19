# Ask My Docs — Frontend

React frontend for the Ask My Docs RAG system.

## Setup

```bash
cd frontend
npm install
npm run dev
```

This starts Vite on `http://localhost:5173` with an API proxy that
forwards `/api/*` requests to `http://localhost:8000` (the FastAPI backend).

Make sure the backend is running first:

```bash
# In the project root
docker-compose up -d
python scripts/setup_db.py
export ANTHROPIC_API_KEY="sk-ant-..."
uvicorn src.api:app --reload
```

## Pages

**Upload page** — Drag-and-drop documents (.md, .html, .txt). Click
"Process files" to send them through the ingestion pipeline. When done,
click "Start chatting" to navigate to the chat.

**Chat page** — Ask questions in natural language. Each AI response shows:
- The answer with inline `[Source N]` citation badges
- A "sources" toggle that expands to show source metadata and the
  full citation report (density bar, pass/fail, uncited sentences)
- Response latency in milliseconds

## Architecture

```
src/
├── api.js                 # All backend fetch calls
├── App.jsx                # Root: header + page routing
├── App.css                # Complete design system
├── pages/
│   ├── UploadPage.jsx     # File upload + processing
│   └── ChatPage.jsx       # Chat interface
└── components/
    ├── DropZone.jsx        # Drag-and-drop area
    ├── FileCard.jsx        # Per-file status display
    ├── MessageBubble.jsx   # Chat message with citation rendering
    └── SourcesPanel.jsx    # Source list + citation report
```

## Production Build

```bash
npm run build     # outputs to dist/
npm run preview   # serve the build locally
```

For production deployment, serve the `dist/` folder from any static
host (Vercel, Netlify, S3 + CloudFront) and update `BASE_URL` in
`src/api.js` to your backend origin.

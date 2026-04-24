# Commander Dashboard

All-in-one agent command center for managing cross-project workflows.

## Quick Start

```bash
# Start all services
docker-compose up

# Or individually:
cd frontend && npm run dev          # http://localhost:3000
cd backend && uvicorn app.main:app  # http://localhost:8000
```

## Development

**👉 See [CLAUDE.md](./CLAUDE.md) for complete development guide**

Key topics:
- 🏗️ Architecture overview
- 🎨 **Component development rules** (use existing, don't copy-paste!)
- 📦 Shared components (ScrollableCard, shadcn/ui)
- 🎯 Common patterns
- 📚 Implementation guides

## Project Structure

```
dashboard/
├── CLAUDE.md              ← 📖 START HERE for development
├── frontend/              # Next.js + React + TypeScript
│   └── src/
│       ├── app/          # Pages (routing)
│       ├── components/
│       │   ├── ui/       # 🔑 Shared UI primitives
│       │   ├── cards/    # Feature cards
│       │   └── ...
│       └── lib/          # API client
├── backend/               # FastAPI + SQLAlchemy
│   └── app/
│       ├── api/          # Routes
│       ├── services/     # Business logic
│       └── models/       # Database models
└── docker-compose.yml
```

## Stack

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **Icons**: Lucide React

## Features

- **Multi-project dashboards**: WX, G4, Jobs, Temporal
- **Agent management**: Session tracking, chat interface
- **JIRA integration**: Ticket summaries, filters
- **GitLab MRs**: Review requests, CI status
- **Real-time data**: Kubernetes deployments, Slack activity
- **Customizable layouts**: Drag-and-drop panels

## Documentation

- **[CLAUDE.md](./CLAUDE.md)** - **Component development guide** 🔑
- [SCROLLABLE-CARD-COMPONENT.md](./SCROLLABLE-CARD-COMPONENT.md) - Shared scrollable card pattern
- [WX-DEPLOYMENTS-IMPLEMENTATION.md](./WX-DEPLOYMENTS-IMPLEMENTATION.md) - K8s integration example
- [JIRA-SUMMARY-IMPLEMENTATION.md](./JIRA-SUMMARY-IMPLEMENTATION.md) - JIRA filters example

## Contributing

Before writing code:

1. ✅ **Read [CLAUDE.md](./CLAUDE.md)** - Understand the component rules
2. ✅ Check for existing components in `frontend/src/components/ui/`
3. ✅ Use shadcn/ui components (don't reinvent buttons, badges, etc.)
4. ✅ Follow established patterns (see implementation docs)
5. ✅ Create `*-IMPLEMENTATION.md` for new features

**Golden Rule**: Reuse and refactor, don't copy-paste.

---

**Questions?** Check [CLAUDE.md](./CLAUDE.md) or existing implementation docs.

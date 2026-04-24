import asyncio
from pathlib import Path
from sqlalchemy import select
from app.database import async_session
from app.models import Agent

async def find():
    async with async_session() as db:
        result = await db.execute(
            select(Agent).where(Agent.message_count > 100).limit(10)
        )
        agents = result.scalars().all()
        
        claude_root = Path.home() / ".claude"
        
        for agent in agents:
            # Check dashboard path
            dashboard_path = claude_root / "sessions" / str(agent.id) / "conversation.jsonl"
            
            # Check VSCode paths
            vscode_paths = []
            if (claude_root / "projects").exists():
                for project_dir in (claude_root / "projects").iterdir():
                    if project_dir.is_dir():
                        vscode_path = project_dir / f"{agent.id}.jsonl"
                        if vscode_path.exists():
                            vscode_paths.append(vscode_path)
            
            if dashboard_path.exists() or vscode_paths:
                path = dashboard_path if dashboard_path.exists() else vscode_paths[0]
                print(f"✅ {agent.id}")
                print(f"   Title: {agent.title[:60]}")
                print(f"   Messages: {agent.message_count}")
                print(f"   Path: {path}")
                print()
                break

if __name__ == "__main__":
    asyncio.run(find())

# Terminal Integration Feature

**Date**: 2026-03-12
**Status**: ✅ Implemented

## Overview

The Terminal Integration feature allows you to quickly open a terminal window in an agent's working directory or worktree directly from the dashboard. This is especially useful for:
- Debugging agent work
- Running commands in the agent's context
- Exploring the worktree/working directory
- Manual interventions

## Features

### 1. Terminal Button on Agent Cards
- Shows on agent cards that have a `worktree_path` or `working_directory`
- Located next to the "Chat" button
- Click to instantly open a terminal in that location
- Disabled state while launching to prevent duplicate opens

### 2. Configurable Terminal Applications

Supported terminal apps (configured in Settings):
- **Ghostty** (default)
- **iTerm2**
- **Terminal.app** (macOS default)
- **Warp**
- **Kitty**
- **Custom** (specify your own command)

### 3. Settings Page Configuration

Navigate to **Settings** to configure your terminal preference:
1. Select from preset terminal applications
2. Or choose "Custom" to specify your own command
3. Use `{path}` as a placeholder for the directory path
4. Settings are stored in browser localStorage

### 4. Smart Path Resolution

- Prefers `worktree_path` over `working_directory`
- If path is a file, opens terminal in parent directory
- Validates path exists before launching
- Expands `~` to home directory

## Architecture

### Frontend

#### New Files
- `hooks/useSettings.ts` - Settings management hook with localStorage persistence
- Updated: `app/settings/page.tsx` - Added Terminal configuration UI
- Updated: `components/agents/AgentRow.tsx` - Added Terminal button

#### Settings Storage
```typescript
interface Settings {
  terminal: {
    app: string;           // "ghostty" | "iterm2" | "terminal" | etc.
    customCommand?: string; // Optional custom command
  };
}
```

Stored in localStorage at key: `dashboard-settings`

### Backend

#### New Files
- `app/api/terminal.py` - Terminal launching API

#### API Endpoint

**POST /api/terminal/launch**

Request:
```json
{
  "path": "/Users/aaryn/workspaces/wx-1",
  "command": "open -a Ghostty {path}"
}
```

Response:
```json
{
  "success": true,
  "path": "/Users/aaryn/workspaces/wx-1",
  "command": "open -a Ghostty /Users/aaryn/workspaces/wx-1"
}
```

#### Security Considerations
- Validates path exists before launching
- Uses `shlex.split()` for safe command parsing
- Launches terminal as detached process
- Logs all terminal launch attempts

## Usage

### Quick Start
1. Go to **Settings** → Terminal Application
2. Select "Ghostty" (or your preferred terminal)
3. Go to **Agents** page
4. Click "Terminal" button on any agent card
5. Terminal opens in the agent's working directory

### Custom Terminal Command

For advanced terminal configurations:
1. Go to Settings → Terminal Application
2. Select "Custom"
3. Enter your command with `{path}` placeholder

Examples:
```bash
# Ghostty with specific options
open -a Ghostty --args --working-directory {path}

# iTerm2 with profile
open -a iTerm --args {path}

# Custom script
/usr/local/bin/my-terminal-launcher.sh {path}
```

## Terminal Commands by App

| App | Command Template |
|-----|------------------|
| Ghostty | `open -a Ghostty {path}` |
| iTerm2 | `open -a iTerm {path}` |
| Terminal.app | `open -a Terminal {path}` |
| Warp | `open -a Warp {path}` |
| Kitty | `open -a Kitty {path}` |

## Troubleshooting

### Terminal doesn't open
1. **Check Settings**: Make sure your terminal app is configured in Settings
2. **Verify App Installed**: The terminal app must be installed on your system
3. **Check Logs**: Look at backend logs for error messages:
   ```bash
   tail -f /tmp/dashboard-backend.log
   ```

### Wrong terminal opens
1. Go to Settings and select the correct terminal app
2. If using Custom, verify the command is correct

### Path issues
- If the agent has no worktree or working directory, the Terminal button won't appear
- Check that the path in the agent card is valid

## Examples

### Opening terminal for a WX agent
1. Agent has `worktree_path: ~/workspaces/wx-1`
2. Click "Terminal" button
3. Ghostty opens with working directory at `~/workspaces/wx-1`
4. You can now run commands like:
   ```bash
   make test
   git status
   wxctl get tasks
   ```

### Opening terminal for a G4 agent
1. Agent has `working_directory: ~/code/product/g4-wk/g4`
2. Click "Terminal" button
3. Terminal opens in the G4 repository
4. Ready for debugging or manual operations

## Future Enhancements

- [ ] Support for different terminal profiles per project
- [ ] Remember last used terminal per project
- [ ] Terminal history/favorites
- [ ] Custom environment variables per terminal launch
- [ ] Integration with tmux/screen sessions
- [ ] Terminal multiplexing support

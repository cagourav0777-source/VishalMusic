# VishalMusic API Reference 🔌

Complete API reference for developers integrating with VishalMusic.

## Overview

VishalMusic provides several APIs and webhooks for integration with external systems.

## Table of Contents

1. [Music Playback API](#music-playback-api)
2. [Search API](#search-api)
3. [Queue API](#queue-api)
4. [Playlist API](#playlist-api)
5. [User API](#user-api)
6. [Statistics API](#statistics-api)
7. [Admin API](#admin-api)
8. [WebHooks](#webhooks)

---

## Music Playback API

### Play Song

```python
# Via Pyrogram Handler
@app.on_message(filters.command("play"))
async def play_song(client, message):
    query = message.text.split(None, 1)[1]
    # Music playing logic
```

### Get Current Playing

```python
# Get currently playing track info
async def get_now_playing(chat_id: int):
    """Get current playing song info"""
    # Returns: {
    #     "title": str,
    #     "artist": str,
    #     "duration": int,
    #     "position": int,
    #     "source": str
    # }
```

### Control Playback

```python
# Pause playback
async def pause_playback(chat_id: int):
    """Pause current playback"""

# Resume playback
async def resume_playback(chat_id: int):
    """Resume paused playback"""

# Skip to next
async def skip_song(chat_id: int):
    """Skip current song"""

# Stop playback
async def stop_playback(chat_id: int):
    """Stop and leave voice chat"""
```

---

## Search API

### YouTube Search

```python
from VISHALMUSIC.platforms.Youtube import download

# Search YouTube
async def search_youtube(query: str, limit: int = 10):
    """
    Search on YouTube
    
    Args:
        query: Search query
        limit: Number of results
        
    Returns:
        List of search results
    """
    results = await download(query, limit)
    return results
```

### Spotify Search

```python
from VISHALMUSIC.platforms.Spotify import search

# Search Spotify
async def search_spotify(query: str):
    """
    Search on Spotify
    
    Args:
        query: Search query or URL
        
    Returns:
        List of tracks with metadata
    """
    results = await search(query)
    return results
```

### Multi-Platform Search

```python
async def search_all_platforms(query: str):
    """
    Search across all platforms
    
    Returns:
        {
            "youtube": [...],
            "spotify": [...],
            "soundcloud": [...],
            "apple": [...]
        }
    """
```

---

## Queue API

### Add to Queue

```python
async def add_to_queue(chat_id: int, song: dict):
    """
    Add song to queue
    
    Args:
        chat_id: Telegram chat ID
        song: Song dictionary with title, url, duration
    """
```

### Remove from Queue

```python
async def remove_from_queue(chat_id: int, position: int):
    """Remove song at position from queue"""
```

### Get Queue

```python
async def get_queue(chat_id: int, page: int = 1):
    """
    Get paginated queue
    
    Returns:
        {
            "songs": [...],
            "total": int,
            "page": int,
            "per_page": int
        }
    """
```

### Clear Queue

```python
async def clear_queue(chat_id: int):
    """Clear entire queue"""
```

### Shuffle Queue

```python
async def shuffle_queue(chat_id: int):
    """Shuffle songs in queue"""
```

---

## Playlist API

### Create Playlist

```python
async def create_playlist(user_id: int, name: str):
    """
    Create new playlist
    
    Returns:
        Playlist ID
    """
```

### Add Song to Playlist

```python
async def add_song_to_playlist(playlist_id: str, song: dict):
    """Add song to playlist"""
```

### Remove Song from Playlist

```python
async def remove_song_from_playlist(playlist_id: str, position: int):
    """Remove song from playlist"""
```

### Get Playlists

```python
async def get_user_playlists(user_id: int):
    """
    Get all playlists for user
    
    Returns:
        List of playlists with metadata
    """
```

### Load Playlist

```python
async def load_playlist(chat_id: int, playlist_id: str):
    """Load and start playing playlist"""
```

### Delete Playlist

```python
async def delete_playlist(playlist_id: str):
    """Delete playlist"""
```

---

## User API

### Get User Info

```python
async def get_user_info(user_id: int):
    """
    Get user information
    
    Returns:
        {
            "user_id": int,
            "username": str,
            "first_name": str,
            "is_admin": bool,
            "is_banned": bool,
            "created_at": datetime,
            "stats": {...}
        }
    """
```

### Update User Settings

```python
async def update_user_settings(user_id: int, settings: dict):
    """
    Update user preferences
    
    Args:
        settings: {
            "language": str,
            "quality": str,
            "theme": str,
            "notifications": bool
        }
    """
```

### Get User Preferences

```python
async def get_user_preferences(user_id: int):
    """Get user settings and preferences"""
```

---

## Statistics API

### Get Bot Stats

```python
async def get_bot_stats():
    """
    Get global bot statistics
    
    Returns:
        {
            "uptime": float,
            "total_users": int,
            "active_chats": int,
            "songs_played": int,
            "total_playtime": int,
            "memory_usage": float,
            "cpu_usage": float
        }
    """
```

### Get User Stats

```python
async def get_user_statistics(user_id: int):
    """
    Get user statistics
    
    Returns:
        {
            "songs_played": int,
            "total_playtime": int,
            "favorite_artist": str,
            "favorite_genre": str,
            "last_played": datetime
        }
    """
```

### Get Chat Stats

```python
async def get_chat_statistics(chat_id: int):
    """
    Get chat/group statistics
    
    Returns:
        {
            "songs_played": int,
            "total_members": int,
            "most_active_user": str,
            "average_song_duration": float
        }
    """
```

---

## Admin API

### Ban User

```python
async def ban_user(user_id: int, reason: str = ""):
    """Ban user from bot"""
```

### Unban User

```python
async def unban_user(user_id: int):
    """Unban user"""
```

### Global Ban

```python
async def global_ban_user(user_id: int, reason: str = ""):
    """Ban user globally from all chats"""
```

### Get Banned Users

```python
async def get_banned_users():
    """Get list of banned users"""
```

### Promote User

```python
async def promote_user(user_id: int):
    """Make user bot admin"""
```

### Demote User

```python
async def demote_user(user_id: int):
    """Remove admin privileges"""
```

---

## WebHooks

### Music Event WebHook

```python
# Webhook format:
POST /webhooks/music

{
    "event": "song_started|song_ended|song_skipped",
    "timestamp": "2026-05-11T12:34:56Z",
    "chat_id": 123456789,
    "user_id": 987654321,
    "song": {
        "title": "Song Title",
        "artist": "Artist Name",
        "duration": 240,
        "source": "youtube"
    }
}
```

### User Event WebHook

```python
POST /webhooks/user

{
    "event": "user_joined|user_left|user_banned",
    "timestamp": "2026-05-11T12:34:56Z",
    "user_id": 987654321,
    "username": "username",
    "reason": "optional reason"
}
```

### Error WebHook

```python
POST /webhooks/errors

{
    "event": "error",
    "timestamp": "2026-05-11T12:34:56Z",
    "error_type": "StreamError",
    "message": "Error description",
    "severity": "warning|error|critical",
    "traceback": "optional full traceback"
}
```

---

## Error Handling

### Error Codes

| Code | Message | Description |
|------|---------|-------------|
| 1001 | SONG_NOT_FOUND | Search returned no results |
| 1002 | INVALID_URL | URL format is invalid |
| 1003 | CONNECTION_ERROR | Network error occurred |
| 1004 | PERMISSION_DENIED | User lacks permission |
| 1005 | INVALID_QUERY | Query is invalid |
| 2001 | DATABASE_ERROR | Database operation failed |
| 2002 | NOT_AUTHORIZED | User not authenticated |
| 3001 | STREAM_ERROR | Audio streaming failed |
| 3002 | DOWNLOAD_ERROR | Download failed |
| 5000 | INTERNAL_ERROR | Server error |

### Error Response Format

```json
{
    "success": false,
    "error": {
        "code": 1001,
        "message": "Song not found",
        "details": "No results for 'invalid query'"
    }
}
```

---

## Rate Limiting

All API calls are rate limited to prevent abuse:

- **Global**: 100 requests per minute
- **Per user**: 10 requests per minute
- **Per chat**: 30 requests per minute

### Rate Limit Headers

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1620000000
```

---

## Authentication

### Bearer Token

```python
headers = {
    "Authorization": "Bearer YOUR_API_TOKEN"
}
```

### API Key

```python
headers = {
    "X-API-Key": "YOUR_API_KEY"
}
```

---

## Examples

### Example 1: Search and Play

```python
async def search_and_play(user_id: int, query: str):
    # Search
    results = await search_youtube(query)
    
    if not results:
        return {"success": False, "error": "No results"}
    
    # Get first result
    song = results[0]
    
    # Add to queue
    await add_to_queue(user_id, song)
    
    return {"success": True, "song": song}
```

### Example 2: Create and Load Playlist

```python
async def create_and_load_playlist(user_id: int, playlist_name: str):
    # Create playlist
    playlist_id = await create_playlist(user_id, playlist_name)
    
    # Search songs
    songs = await search_spotify("top hits")
    
    # Add songs to playlist
    for song in songs[:10]:
        await add_song_to_playlist(playlist_id, song)
    
    # Load playlist
    await load_playlist(user_id, playlist_id)
    
    return {"success": True, "playlist_id": playlist_id}
```

### Example 3: Get Statistics

```python
async def get_all_stats():
    bot_stats = await get_bot_stats()
    
    return {
        "bot": bot_stats,
        "timestamp": datetime.now().isoformat()
    }
```

---

## SDK & Libraries

Official SDKs coming soon in:
- Python
- JavaScript/Node.js
- Go
- Rust

---

## Support

- 📖 Documentation: [README.md](README.md)
- 💬 Support: @ItsMeVishalSupport
- 🐛 Issues: GitHub Issues
- 👨‍💻 Owner: @Its_me_Vishall

---

**Last updated:** 2026-05-11

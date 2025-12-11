# ClubGallery Architecture

Photo gallery system for Wild Apricot organizations with AI-powered tagging and face recognition.

**Repository:** https://github.com/sbnctech/clubgallery

## Design Principles

- **Easy Maintenance**: Simple architecture with minimal moving parts. SQLite database, straightforward Python/Flask backend, no complex infrastructure
- **Externalized Configuration**: All customization knobs in `.env` and database settings - no code changes needed for tuning behavior
- **Rigorous Standards**: Consistent coding patterns, clear separation of concerns, testable components
- **Read-Only WA Integration**: Never modifies Wild Apricot data - only reads members, events, and registrations
- **Progressive Automation**: AI handles tedious tasks (face matching, event detection) while humans confirm important decisions

### Configuration Philosophy

Customization should happen through configuration, not code:

| Setting | Location | Purpose |
|---------|----------|---------|
| API credentials | `.env` | WA API key, IMAP credentials |
| Face match thresholds | `.env` | Confidence levels for auto-tagging |
| Processing options | `.env` | Thumbnail sizes, GPS matching radius |
| Organization settings | Database | Activity groups, tag categories |
| Admin permissions | Database | User roles and access levels |

## System Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Photo Sources  │     │   Processing    │     │    Display      │
│  - Email        │ ──► │   Pipeline      │ ──► │  - Gallery      │
│  - Web Upload   │     │                 │     │  - Admin UI     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
                    ┌─────────────────────┐
                    │   Wild Apricot      │
                    │  - Members          │
                    │  - Events           │
                    │  - Registrations    │
                    └─────────────────────┘
```

## Core Components

### 1. Photo Ingestion (`app/ingest/`)

Two intake methods for photos:

| Component | File | Purpose |
|-----------|------|---------|
| Email Monitor | `email_monitor.py` | IMAP inbox scanning for photo attachments |
| Upload Handler | `upload_handler.py` | Web-based photo uploads |
| Queue Manager | `queue_manager.py` | Processing queue management |

### 2. AI Processing Pipeline (`app/processing/`)

Photos flow through a multi-step processing pipeline:

```
Photo ──► EXIF ──► Event ──► Face ──► Thumbnail ──► Tags
         Extract   Match    Detect    Create       Generate
```

| Step | File | Description |
|------|------|-------------|
| EXIF Extraction | `exif_extractor.py` | Date, GPS, camera metadata |
| Event Matching | `event_matcher.py` | Match GPS/date to WA events |
| Face Detection | `face_detector.py` | Find faces using dlib |
| Face Recognition | `face_detector.py` | Match faces to members |
| Thumbnails | `thumbnail_creator.py` | Generate display sizes |
| Tag Generation | `tag_generator.py` | Create searchable tags |
| Pipeline | `pipeline.py` | Orchestrates full workflow |

### 3. Wild Apricot Sync (`app/sync/`)

Keeps local data synchronized with Wild Apricot:

| Component | File | Purpose |
|-----------|------|---------|
| WA API Client | `wa_api.py` | Wild Apricot API wrapper |
| Member Sync | `member_sync.py` | Sync members, events, registrations |
| WebDAV Backup | `wa_webdav.py` | Backup photos to WA storage |

### 4. Admin Interface (`app/admin/`)

Web interface for photo review and management:

- **Dashboard** - Overview of queue status
- **Review Queue** - Pending photos awaiting approval
- **Photo Editor** - Face tagging and metadata editing
- **Settings** - Configuration management

### 5. Public Gallery (`app/gallery/`)

nanogallery2-based display widget:

- **Gallery Page** - Main photo display
- **Widget JS** - Embeddable gallery widget
- **API Endpoints** - JSON feeds for gallery data

## Data Model

### SQLite Database (`data/clubgallery.db`)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   photos     │     │    faces     │     │   members    │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id           │◄────│ photo_id     │     │ id           │
│ file_path    │     │ member_id    │────►│ wa_id        │
│ event_id     │     │ confidence   │     │ name         │
│ taken_at     │     │ confirmed    │     │ photo_url    │
│ gps_lat/lon  │     │ x, y, w, h   │     │ encoding     │
│ status       │     └──────────────┘     └──────────────┘
│ approved     │
└──────────────┘
        │
        ▼
┌──────────────┐     ┌──────────────┐
│    events    │     │ registrations│
├──────────────┤     ├──────────────┤
│ id           │◄────│ event_id     │
│ wa_id        │     │ member_id    │
│ name         │     │ status       │
│ start_date   │     └──────────────┘
│ location     │
│ gps_lat/lon  │
└──────────────┘
```

### Photo Status Flow

```
uploaded ──► queued ──► processing ──► pending_review ──► approved
                                              │
                                              └──► rejected
```

## Face Recognition Logic

1. **Build Face Database** - Extract face encodings from member profile photos
2. **Detect Faces** - Find all faces in uploaded photo
3. **Match Faces** - Compare to known member encodings
4. **Prioritize RSVPs** - Weight matches toward event registrants
5. **Confidence Scoring** - High confidence auto-tags, low requires review

### Confidence Thresholds

| Level | Threshold | Action |
|-------|-----------|--------|
| High | < 0.4 | Auto-tag member |
| Medium | 0.4 - 0.6 | Suggest match, require confirmation |
| Low | > 0.6 | No match suggested |

## API Endpoints

### Public Gallery API

| Endpoint | Description |
|----------|-------------|
| `GET /api/gallery.json` | Photo data for nanogallery2 |
| `GET /api/events.json` | Events for filtering |
| `GET /api/members.json` | Members for search |
| `GET /api/activities.json` | Activity groups |

### Admin API

| Endpoint | Description |
|----------|-------------|
| `GET /admin/` | Dashboard |
| `GET /admin/queue` | Review queue |
| `GET /admin/photo/<id>` | Photo editor |
| `POST /admin/photo/<id>/face` | Update face identification |
| `POST /admin/photo/<id>/approve` | Approve photo for gallery |

## File Storage

```
photos/
├── originals/          # Full-size uploads
├── thumbnails/         # Display sizes
│   ├── small/          # 200px
│   ├── medium/         # 800px
│   └── large/          # 1600px
└── faces/              # Cropped face images
```

## Deployment

### Development

```bash
python app/main.py
```

Runs Flask development server on http://localhost:5000

### Production

- **Nginx** - Reverse proxy and static file serving
- **Gunicorn** - WSGI application server
- **systemd** - Process management
- **Cron** - Scheduled sync and email monitoring

## Related Projects

- [clubcalendar](https://github.com/sbnctech/clubcalendar) - Event calendar widget for Wild Apricot

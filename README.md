# ClubGallery

Photo gallery widget and management system for Wild Apricot organizations. Features AI-powered tagging, face recognition, event matching, and an embeddable gallery widget.

**Repository:** https://github.com/sbnctech/clubgallery

## Features

- **Photo Submission**: Accept photos via email or web upload
- **AI Processing**: Automatic EXIF extraction, GPS-based event matching, face recognition
- **Face Recognition**: Match faces to members, prioritize event RSVPs
- **Admin Review**: Web interface for approving photos and confirming face IDs
- **Gallery Widget**: nanogallery2-based display with filtering by member, event, activity, year
- **Wild Apricot Integration**: Sync members, events, and registrations

## Requirements

- Python 3.10+
- SQLite (built-in)
- System packages:
  - cmake, boost (for dlib/face_recognition)
  - exiftool (for EXIF writing)

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# System dependencies
# Ubuntu: sudo apt install cmake libboost-all-dev libimage-exiftool-perl
# macOS: brew install cmake boost exiftool
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Initialize Database

```bash
python -c "from app.database import init_db; init_db()"
```

### 4. Create Admin User

```bash
python -c "from app.main import create_admin_user; create_admin_user('admin@example.com', 'password', is_super_admin=True)"
```

### 5. Initial Data Sync

```bash
# Sync members and events from Wild Apricot
python scripts/sync_wa_data.py

# Build face database from member photos
python scripts/build_face_database.py
```

### 6. Run Development Server

```bash
python app/main.py
```

Visit:
- Gallery: http://localhost:5000/gallery
- Admin: http://localhost:5000/admin
- Upload: http://localhost:5000/upload

## Project Structure

```
clubgallery/
├── app/
│   ├── config.py              # Configuration
│   ├── database.py            # SQLite database
│   ├── main.py                # Flask app factory
│   ├── ingest/                # Photo ingestion
│   │   ├── email_monitor.py   # IMAP inbox processing
│   │   ├── upload_handler.py  # Web uploads
│   │   └── queue_manager.py   # Processing queue
│   ├── processing/            # AI processing
│   │   ├── exif_extractor.py  # EXIF metadata
│   │   ├── event_matcher.py   # GPS/date event matching
│   │   ├── face_detector.py   # Face recognition
│   │   ├── thumbnail_creator.py
│   │   ├── tag_generator.py
│   │   └── pipeline.py        # Full processing workflow
│   ├── sync/                  # Wild Apricot sync
│   │   ├── wa_api.py          # WA API client
│   │   ├── member_sync.py     # Member/event sync
│   │   └── wa_webdav.py       # WebDAV backup
│   ├── admin/                 # Admin interface
│   │   ├── routes.py
│   │   ├── auth.py
│   │   ├── templates/
│   │   └── static/
│   └── gallery/               # Public gallery
│       ├── routes.py
│       ├── static/sbnc-gallery-widget.js
│       └── templates/
├── scripts/                   # Utility scripts
├── data/                      # SQLite database (gitignored)
├── photos/                    # Photo storage (gitignored)
├── requirements.txt
└── .env                       # Configuration (gitignored)
```

## Photo Workflow

1. **Submission**: Photo received via email or web upload
2. **Queue**: Added to processing queue
3. **EXIF Extraction**: Date, GPS, camera info extracted
4. **Event Matching**: Match to WA event by date + GPS
5. **Face Detection**: Find all faces in photo
6. **Face Recognition**: Match faces to members (prioritize event RSVPs)
7. **Tag Generation**: Create searchable tags
8. **Admin Review**: Confirm face IDs, approve for publishing
9. **Gallery**: Display in public gallery with smart filtering

## API Endpoints

### Gallery API
- `GET /api/gallery.json` - Gallery data for nanogallery2
- `GET /api/events.json` - Events list for filters
- `GET /api/members.json` - Members list for search
- `GET /api/activities.json` - Activity groups

### Admin API
- `GET /admin/` - Dashboard
- `GET /admin/queue` - Review queue
- `GET /admin/photo/<id>` - Photo editor
- `POST /admin/photo/<id>/face` - Update face ID
- `POST /admin/photo/<id>/approve` - Approve photo

## Configuration

See `.env.example` for all configuration options.

Key settings:
- `WA_API_KEY` - Wild Apricot API key
- `WA_ACCOUNT_ID` - Wild Apricot account ID
- `IMAP_HOST` - Email server for photo submissions
- `IMAP_USER` - Email account username
- `IMAP_PASSWORD` - Email account password
- `FACE_MATCH_HIGH_CONFIDENCE` - Threshold for auto-tagging (default 0.4)

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System design and data model
- [Wild Apricot Embed Instructions](docs/WA-EMBED-INSTRUCTIONS.md) - Embedding the widget

## Production Deployment

See `docs/` for deployment guides:

- Nginx configuration
- Gunicorn/systemd setup
- Cron job scheduling

## Related Projects

- [clubcalendar](https://github.com/sbnctech/clubcalendar) - Event calendar widget for Wild Apricot

## License

MIT License - see LICENSE file

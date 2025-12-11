# SBNC AI-Powered Photo Gallery System

An AI-powered photo management system for Santa Barbara Newcomers Club that automatically tags photos using face recognition, GPS, and date/time, matches them to events, and provides a searchable gallery.

## Features

- **Photo Submission**: Accept photos via email (photos@sbnewcomers.org) or web upload
- **AI Processing**: Automatic EXIF extraction, GPS-based event matching, face recognition
- **Face Recognition**: Match faces to SBNC members, prioritize event RSVPs
- **Admin Review**: Web interface for approving photos and confirming face IDs
- **Smart Gallery**: nanogallery2-based display with filtering by member, event, activity, year
- **WA Integration**: Sync members, events, and registrations from Wild Apricot

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install -r requirements.txt

# Note: face_recognition requires dlib which needs cmake
# On Ubuntu: sudo apt install cmake libboost-all-dev
# On macOS: brew install cmake boost
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

## Production Deployment

### Server Setup (mail.sbnewcomers.org)

```bash
# Create user and directory
sudo useradd -m -s /bin/bash sbnc
sudo mkdir -p /home/sbnc-photos /var/www/photos /var/log/sbnc-photos
sudo chown sbnc:sbnc /home/sbnc-photos /var/www/photos /var/log/sbnc-photos

# Clone/copy project
sudo -u sbnc git clone <repo> /home/sbnc-photos
# Or: sudo cp -r /path/to/sbnc-photos /home/sbnc-photos

# Setup virtualenv
sudo -u sbnc python3 -m venv /home/sbnc-photos/venv
sudo -u sbnc /home/sbnc-photos/venv/bin/pip install -r /home/sbnc-photos/requirements.txt
```

### Nginx Configuration

```nginx
server {
    listen 443 ssl;
    server_name photos.sbnewcomers.org;

    ssl_certificate /etc/letsencrypt/live/photos.sbnewcomers.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/photos.sbnewcomers.org/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /photos/ {
        alias /var/www/photos/;
        expires 1d;
    }
}
```

### Gunicorn Service

Create `/etc/systemd/system/sbnc-photos.service`:

```ini
[Unit]
Description=SBNC Photo Gallery
After=network.target

[Service]
User=sbnc
Group=sbnc
WorkingDirectory=/home/sbnc-photos
Environment="PATH=/home/sbnc-photos/venv/bin"
ExecStart=/home/sbnc-photos/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 app.main:create_app()

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable sbnc-photos
sudo systemctl start sbnc-photos
```

### Cron Jobs

```bash
sudo cp cron.example /etc/cron.d/sbnc-photos
```

## Project Structure

```
sbnc-photos/
├── app/
│   ├── __init__.py
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
│       └── templates/
├── scripts/                   # Cron scripts
├── data/                      # SQLite database
├── photos/                    # Photo storage
├── requirements.txt
└── .env
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

## Photo Status

- **Awaiting Approval**: New uploads, not visible to members
- **Members Only**: Approved, visible to logged-in members
- **Public**: Approved for public/marketing use
- **Do Not Post**: Rejected or removal requested

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
- `POST /admin/flash-process` - Trigger processing

## Configuration

See `.env.example` for all configuration options.

Key settings:
- `WA_API_KEY` - Wild Apricot API key
- `IMAP_PASSWORD` - Email account password
- `FACE_MATCH_HIGH_CONFIDENCE` - Threshold for auto-tagging (default 0.4)

## Troubleshooting

### Face recognition not working
- Ensure dlib is installed correctly
- Run `python scripts/build_face_database.py` to rebuild embeddings
- Check member profile photos exist in WA

### Photos not matching to events
- Verify events are synced: `python scripts/sync_wa_data.py`
- Check photo has GPS data in EXIF
- Event locations may need geocoding

### Email not processing
- Verify IMAP credentials in .env
- Check email server allows IMAP access
- Review logs: `/var/log/sbnc-photos/email.log`

## License

Proprietary - Santa Barbara Newcomers Club

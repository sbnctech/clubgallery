"""
SBNC Photo Gallery System - Database Module
SQLite database connection and schema management.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from app.config import DATABASE_PATH


def get_connection():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize the database with the required schema."""
    with get_db() as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialized at {DATABASE_PATH}")


SCHEMA = """
-- Members (synced from Wild Apricot)
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,                    -- WA member ID
    email TEXT,
    first_name TEXT,
    last_name TEXT,
    display_name TEXT,
    profile_photo_url TEXT,
    directory_headshot_url TEXT,            -- Primary source for face recognition
    face_recognition_opt_out BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_members_email ON members(email);
CREATE INDEX IF NOT EXISTS idx_members_name ON members(last_name, first_name);

-- Face embeddings for recognition
CREATE TABLE IF NOT EXISTS face_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT REFERENCES members(id) ON DELETE CASCADE,
    embedding BLOB,                         -- 128-dim vector as bytes
    source TEXT,                            -- 'profile', 'directory', 'confirmed', 'self-tag'
    quality_score REAL,                     -- Quality metric for the embedding
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_face_embeddings_member ON face_embeddings(member_id);

-- Events (synced from Wild Apricot)
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,                    -- WA event ID
    name TEXT NOT NULL,
    description TEXT,
    start_date TIMESTAMP,
    end_date TIMESTAMP,
    location_name TEXT,
    location_address TEXT,
    location_lat REAL,
    location_lon REAL,
    activity_group TEXT,                    -- Happy Hikers, Golf, Wine Club, etc.
    is_public BOOLEAN DEFAULT FALSE,        -- Public events may have non-member attendees
    cover_photo_id TEXT,                    -- Reference to a photo for the event cover
    photo_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_date ON events(start_date);
CREATE INDEX IF NOT EXISTS idx_events_activity ON events(activity_group);

-- Event Registrations/RSVPs (synced from Wild Apricot)
CREATE TABLE IF NOT EXISTS event_registrations (
    event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
    member_id TEXT REFERENCES members(id) ON DELETE CASCADE,
    registration_type TEXT,                 -- 'attending', 'waitlist', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, member_id)
);

-- Photos
CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,                    -- UUID
    original_filename TEXT,
    submitter_member_id TEXT REFERENCES members(id),
    submitter_email TEXT,                   -- For non-member submissions
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submitted_via TEXT,                     -- 'email', 'upload', 'wa_sync'

    -- EXIF data
    taken_at TIMESTAMP,
    gps_lat REAL,
    gps_lon REAL,
    camera_make TEXT,
    camera_model TEXT,

    -- Event matching
    event_id TEXT REFERENCES events(id),
    event_match_confidence REAL,            -- 0.0 to 1.0
    event_match_method TEXT,                -- 'gps', 'date', 'manual', 'submitter_rsvp'

    -- Processing status
    processed_at TIMESTAMP,
    processing_error TEXT,

    -- Review status
    status TEXT DEFAULT 'awaiting_approval',  -- awaiting_approval, members_only, public, do_not_post
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    review_notes TEXT,

    -- Caption (optional, shown if widget has "show captions" enabled)
    caption TEXT,

    -- Storage paths (relative to PHOTO_STORAGE_ROOT)
    original_path TEXT,
    display_path TEXT,
    thumb_path TEXT,

    -- Metadata
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    content_hash TEXT,                      -- SHA-256 hash for duplicate detection

    -- WA Export tracking
    exported_to_wa INTEGER DEFAULT 0,       -- 1 if exported to WA file storage
    exported_at TIMESTAMP,                  -- When exported
    wa_export_path TEXT,                    -- Path in WA file storage

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_photos_status ON photos(status);
CREATE INDEX IF NOT EXISTS idx_photos_event ON photos(event_id);
CREATE INDEX IF NOT EXISTS idx_photos_submitter ON photos(submitter_member_id);
CREATE INDEX IF NOT EXISTS idx_photos_taken_at ON photos(taken_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_content_hash ON photos(content_hash);

-- Detected faces in photos
CREATE TABLE IF NOT EXISTS photo_faces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id TEXT REFERENCES photos(id) ON DELETE CASCADE,

    -- Bounding box (pixel coordinates)
    box_top INTEGER,
    box_right INTEGER,
    box_bottom INTEGER,
    box_left INTEGER,

    -- Face embedding for matching
    embedding BLOB,                         -- 128-dim vector as bytes

    -- Recognition results
    matched_member_id TEXT REFERENCES members(id),
    match_confidence REAL,                  -- Distance score (lower = better match)
    match_rank INTEGER,                     -- Rank among candidates (1 = best)

    -- Top candidates for review (JSON array)
    candidates_json TEXT,

    -- Admin confirmation
    confirmed BOOLEAN DEFAULT FALSE,
    confirmed_member_id TEXT REFERENCES members(id),  -- Final confirmed identity
    confirmed_by TEXT,                      -- Admin who confirmed
    confirmed_at TIMESTAMP,
    is_guest BOOLEAN DEFAULT FALSE,         -- Marked as non-member guest

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_photo_faces_photo ON photo_faces(photo_id);
CREATE INDEX IF NOT EXISTS idx_photo_faces_member ON photo_faces(matched_member_id);
CREATE INDEX IF NOT EXISTS idx_photo_faces_confirmed ON photo_faces(confirmed_member_id);

-- Tags for photos
CREATE TABLE IF NOT EXISTS photo_tags (
    photo_id TEXT REFERENCES photos(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    tag_type TEXT,                          -- 'event', 'activity', 'date', 'person', 'location', 'submitter'
    auto_generated BOOLEAN DEFAULT TRUE,    -- FALSE if manually added
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (photo_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_photo_tags_tag ON photo_tags(tag);
CREATE INDEX IF NOT EXISTS idx_photo_tags_type ON photo_tags(tag_type);

-- Processing queue for incoming photos
CREATE TABLE IF NOT EXISTS processing_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_path TEXT NOT NULL,               -- Path to the uploaded file
    submitter_email TEXT,
    submitter_member_id TEXT REFERENCES members(id),
    source TEXT,                            -- 'email', 'upload'
    original_filename TEXT,

    -- Processing status
    status TEXT DEFAULT 'pending',          -- pending, processing, completed, failed
    priority INTEGER DEFAULT 0,             -- Higher = process first
    attempts INTEGER DEFAULT 0,
    error_message TEXT,

    -- Timestamps
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_processing_queue_priority ON processing_queue(priority DESC, submitted_at ASC);

-- Activity groups (cached from WA for faster lookups)
CREATE TABLE IF NOT EXISTS activity_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    icon TEXT,                              -- Emoji or icon identifier
    event_count INTEGER DEFAULT 0,
    photo_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Admin users (for the review interface)
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id TEXT REFERENCES members(id),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,                     -- For local auth; NULL if using WA OAuth
    is_active BOOLEAN DEFAULT TRUE,
    is_super_admin BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log for tracking admin actions
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user_id INTEGER REFERENCES admin_users(id),
    action TEXT NOT NULL,                   -- 'approve', 'reject', 'identify_face', etc.
    entity_type TEXT,                       -- 'photo', 'face', 'member'
    entity_id TEXT,
    old_value TEXT,                         -- JSON of previous state
    new_value TEXT,                         -- JSON of new state
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_admin ON audit_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);

-- Sync status tracking
CREATE TABLE IF NOT EXISTS sync_status (
    sync_type TEXT PRIMARY KEY,             -- 'members', 'events', 'registrations', 'webdav'
    last_sync_at TIMESTAMP,
    last_sync_status TEXT,                  -- 'success', 'failed'
    last_error TEXT,
    items_synced INTEGER DEFAULT 0
);

-- Initialize default sync status entries
INSERT OR IGNORE INTO sync_status (sync_type) VALUES ('members');
INSERT OR IGNORE INTO sync_status (sync_type) VALUES ('events');
INSERT OR IGNORE INTO sync_status (sync_type) VALUES ('registrations');
INSERT OR IGNORE INTO sync_status (sync_type) VALUES ('webdav');
"""


def dict_from_row(row):
    """Convert a sqlite3.Row to a dictionary."""
    if row is None:
        return None
    return dict(row)


def get_member_by_id(member_id):
    """Get a member by their WA ID."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM members WHERE id = ?',
            (member_id,)
        ).fetchone()
        return dict_from_row(row)


def get_member_by_email(email):
    """Get a member by their email address."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT * FROM members WHERE email = ? COLLATE NOCASE',
            (email,)
        ).fetchone()
        return dict_from_row(row)


def get_pending_photos():
    """Get all photos awaiting approval."""
    with get_db() as conn:
        rows = conn.execute('''
            SELECT p.*, e.name as event_name, m.display_name as submitter_name
            FROM photos p
            LEFT JOIN events e ON p.event_id = e.id
            LEFT JOIN members m ON p.submitter_member_id = m.id
            WHERE p.status = 'awaiting_approval'
            ORDER BY p.submitted_at DESC
        ''').fetchall()
        return [dict_from_row(row) for row in rows]


def get_photo_with_faces(photo_id):
    """Get a photo with all its detected faces."""
    with get_db() as conn:
        photo = conn.execute(
            'SELECT * FROM photos WHERE id = ?',
            (photo_id,)
        ).fetchone()

        if not photo:
            return None

        faces = conn.execute('''
            SELECT pf.*, m.display_name as matched_name, m.profile_photo_url
            FROM photo_faces pf
            LEFT JOIN members m ON pf.matched_member_id = m.id
            WHERE pf.photo_id = ?
            ORDER BY pf.box_left
        ''', (photo_id,)).fetchall()

        result = dict_from_row(photo)
        result['faces'] = [dict_from_row(f) for f in faces]
        return result


def update_photo_status(photo_id, status, reviewed_by=None, notes=None):
    """Update the status of a photo."""
    with get_db() as conn:
        conn.execute('''
            UPDATE photos
            SET status = ?, reviewed_by = ?, reviewed_at = ?, review_notes = ?, updated_at = ?
            WHERE id = ?
        ''', (status, reviewed_by, datetime.utcnow(), notes, datetime.utcnow(), photo_id))


def confirm_face_identity(face_id, member_id, confirmed_by, is_guest=False):
    """Confirm or correct a face identification."""
    with get_db() as conn:
        conn.execute('''
            UPDATE photo_faces
            SET confirmed = TRUE,
                confirmed_member_id = ?,
                confirmed_by = ?,
                confirmed_at = ?,
                is_guest = ?
            WHERE id = ?
        ''', (member_id, confirmed_by, datetime.utcnow(), is_guest, face_id))


if __name__ == '__main__':
    init_db()

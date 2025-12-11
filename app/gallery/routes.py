"""
SBNC Photo Gallery System - Gallery Routes
Public gallery display and API endpoints.
"""

from flask import Blueprint, render_template, request, jsonify, send_from_directory
import json
import logging

from app.database import get_db
from app.config import PHOTO_STORAGE_ROOT, PhotoStatus

logger = logging.getLogger(__name__)

gallery_bp = Blueprint('gallery', __name__, static_folder='static', template_folder='templates')


@gallery_bp.route('/gallery')
def gallery_page():
    """Main gallery page (members view - shows all approved photos)."""
    return render_template('gallery/gallery.html', access='members')


@gallery_bp.route('/gallery/embed')
def gallery_embed():
    """Iframe-friendly gallery page (members view)."""
    return render_template('gallery/embed.html', access='members')


@gallery_bp.route('/gallery/public')
def gallery_public():
    """Public gallery page (shows only public photos)."""
    return render_template('gallery/gallery_public.html', access='public')


@gallery_bp.route('/gallery/public/embed')
def gallery_public_embed():
    """Iframe-friendly public gallery page."""
    return render_template('gallery/embed_public.html', access='public')


@gallery_bp.route('/gallery/widget.js')
def gallery_widget():
    """Serve the gallery widget JavaScript."""
    return send_from_directory(
        gallery_bp.static_folder,
        'sbnc-gallery-widget.js',
        mimetype='application/javascript'
    )


@gallery_bp.route('/api/gallery.json')
def gallery_data():
    """
    Gallery data API for nanogallery2.

    Query params:
        - member: Filter by member ID
        - event: Filter by event ID
        - activity: Filter by activity group
        - year: Filter by year
        - access: 'public' for public-only, 'members' for all approved (default)
    """
    member_id = request.args.get('member')
    event_id = request.args.get('event')
    activity = request.args.get('activity')
    year = request.args.get('year')
    access = request.args.get('access', 'members')

    # Public access shows only public photos
    # Member access shows members_only + public
    if access == 'public':
        status_filter = "status = 'public'"
    else:
        status_filter = "(status = 'members_only' OR status = 'public')"

    # Build query based on filters
    if event_id:
        # Return photos for a specific event
        return _get_event_photos(event_id, status_filter)
    elif member_id:
        # Return photos of a specific member, grouped by event
        return _get_member_photos(member_id, activity, status_filter)
    elif activity:
        # Return events in an activity group
        return _get_activity_events(activity, year, status_filter)
    elif year:
        # Return events from a specific year
        return _get_year_events(year, status_filter)
    else:
        # Return all events as albums
        return _get_all_events(status_filter)


def _get_all_events(status_filter):
    """Get all events as album covers."""
    with get_db() as conn:
        events = conn.execute(f'''
            SELECT e.id, e.name, e.start_date, e.activity_group,
                   (SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id AND {status_filter}) as photo_count,
                   (SELECT p.thumb_path FROM photos p WHERE p.event_id = e.id AND {status_filter} LIMIT 1) as cover_thumb
            FROM events e
            WHERE EXISTS (SELECT 1 FROM photos p WHERE p.event_id = e.id AND {status_filter})
            ORDER BY e.start_date DESC
        ''').fetchall()

    albums = []
    for event in events:
        if event['photo_count'] > 0:
            thumb_path = f"/photos/thumbs/{event['cover_thumb']}" if event['cover_thumb'] else ''
            albums.append({
                'ID': event['id'],  # nanogallery2 requires uppercase ID
                'albumID': '0',  # Root level album
                'title': event['name'],
                'description': f"{event['start_date'][:10] if event['start_date'] else ''} • {event['photo_count']} photos",
                'kind': 'album',
                'src': thumb_path,
                'srct': thumb_path,
                'activity': event['activity_group']
            })

    return jsonify(albums)


def _get_event_photos(event_id, status_filter):
    """Get all photos for a specific event."""
    with get_db() as conn:
        # Get event info
        event = conn.execute(
            'SELECT * FROM events WHERE id = ?',
            (event_id,)
        ).fetchone()

        if not event:
            return jsonify([])

        # Get photos
        photos = conn.execute(f'''
            SELECT p.id, p.thumb_path, p.display_path, p.taken_at,
                   (SELECT GROUP_CONCAT(m.display_name, ', ')
                    FROM photo_faces pf
                    JOIN members m ON pf.confirmed_member_id = m.id
                    WHERE pf.photo_id = p.id AND pf.confirmed = TRUE AND pf.is_guest = FALSE
                   ) as people
            FROM photos p
            WHERE p.event_id = ? AND {status_filter}
            ORDER BY p.taken_at
        ''', (event_id,)).fetchall()

    items = []
    for photo in photos:
        items.append({
            'id': photo['id'],
            'albumID': event_id,  # Link photo to its album
            'src': f"/photos/display/{photo['display_path']}",
            'srct': f"/photos/thumbs/{photo['thumb_path']}",
            'title': photo['people'] or '',
            'description': photo['taken_at'][:16] if photo['taken_at'] else ''
        })

    return jsonify(items)


def _get_member_photos(member_id, activity, status_filter):
    """Get photos containing a specific member, grouped by event."""
    with get_db() as conn:
        # Build activity filter
        activity_filter = ""
        params = [member_id]
        if activity:
            activity_filter = "AND e.activity_group = ?"
            params.append(activity)

        # Get photos grouped by event
        photos = conn.execute(f'''
            SELECT p.id, p.thumb_path, p.display_path, p.taken_at,
                   e.id as event_id, e.name as event_name, e.start_date
            FROM photos p
            JOIN photo_faces pf ON p.id = pf.photo_id
            JOIN events e ON p.event_id = e.id
            WHERE (pf.confirmed_member_id = ? OR pf.matched_member_id = ?)
            AND {status_filter}
            {activity_filter}
            ORDER BY e.start_date DESC, p.taken_at
        ''', params + params[:1]).fetchall()

    # Group by event
    events = {}
    for photo in photos:
        event_id = photo['event_id']
        if event_id not in events:
            events[event_id] = {
                'id': event_id,
                'title': photo['event_name'],
                'description': photo['start_date'][:10] if photo['start_date'] else '',
                'kind': 'album',
                'albumID': f"member-{member_id}-{event_id}",
                'items': []
            }

        events[event_id]['items'].append({
            'id': photo['id'],
            'src': f"/photos/display/{photo['display_path']}",
            'srct': f"/photos/thumbs/{photo['thumb_path']}"
        })

    # Add thumbnail from first photo
    for event in events.values():
        if event['items']:
            event['srct'] = event['items'][0]['srct']

    return jsonify(list(events.values()))


def _get_activity_events(activity, year, status_filter):
    """Get events for a specific activity group."""
    with get_db() as conn:
        year_filter = ""
        params = [activity]
        if year:
            year_filter = "AND strftime('%Y', e.start_date) = ?"
            params.append(year)

        events = conn.execute(f'''
            SELECT e.id, e.name, e.start_date, e.activity_group,
                   (SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id AND {status_filter}) as photo_count,
                   (SELECT p.thumb_path FROM photos p WHERE p.event_id = e.id AND {status_filter} LIMIT 1) as cover_thumb
            FROM events e
            WHERE e.activity_group = ?
            AND EXISTS (SELECT 1 FROM photos p WHERE p.event_id = e.id AND {status_filter})
            {year_filter}
            ORDER BY e.start_date DESC
        ''', params).fetchall()

    albums = []
    for event in events:
        thumb_path = f"/photos/thumbs/{event['cover_thumb']}" if event['cover_thumb'] else ''
        albums.append({
            'ID': event['id'],  # nanogallery2 requires uppercase ID
            'albumID': '0',  # Root level album
            'title': event['name'],
            'description': f"{event['start_date'][:10] if event['start_date'] else ''} • {event['photo_count']} photos",
            'kind': 'album',
            'src': thumb_path,
            'srct': thumb_path
        })

    return jsonify(albums)


def _get_year_events(year, status_filter):
    """Get events from a specific year."""
    with get_db() as conn:
        events = conn.execute(f'''
            SELECT e.id, e.name, e.start_date, e.activity_group,
                   (SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id AND {status_filter}) as photo_count,
                   (SELECT p.thumb_path FROM photos p WHERE p.event_id = e.id AND {status_filter} LIMIT 1) as cover_thumb
            FROM events e
            WHERE strftime('%Y', e.start_date) = ?
            AND EXISTS (SELECT 1 FROM photos p WHERE p.event_id = e.id AND {status_filter})
            ORDER BY e.start_date DESC
        ''', (year,)).fetchall()

    albums = []
    for event in events:
        thumb_path = f"/photos/thumbs/{event['cover_thumb']}" if event['cover_thumb'] else ''
        albums.append({
            'ID': event['id'],  # nanogallery2 requires uppercase ID
            'albumID': '0',  # Root level album
            'title': event['name'],
            'description': f"{event['start_date'][:10] if event['start_date'] else ''} • {event['photo_count']} photos",
            'kind': 'album',
            'src': thumb_path,
            'srct': thumb_path,
            'activity': event['activity_group']
        })

    return jsonify(albums)


@gallery_bp.route('/api/events.json')
def events_list():
    """Get list of events for filter dropdown.

    Query params:
        - access: 'public' for public-only, 'members' for all approved (default)
    """
    access = request.args.get('access', 'members')

    if access == 'public':
        status_filter = "p.status = 'public'"
    else:
        status_filter = "(p.status = 'members_only' OR p.status = 'public')"

    with get_db() as conn:
        events = conn.execute(f'''
            SELECT e.id, e.name, e.start_date, e.activity_group,
                   (SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id
                    AND {status_filter}) as photo_count
            FROM events e
            WHERE EXISTS (SELECT 1 FROM photos p WHERE p.event_id = e.id
                          AND {status_filter})
            ORDER BY e.start_date DESC
        ''').fetchall()

    result = []
    for event in events:
        result.append({
            'id': event['id'],
            'name': event['name'],
            'date': event['start_date'][:10] if event['start_date'] else '',
            'activity': event['activity_group'],
            'photoCount': event['photo_count']
        })

    return jsonify(result)


@gallery_bp.route('/api/members.json')
def members_list():
    """Get list of members with photo counts for search."""
    with get_db() as conn:
        members = conn.execute('''
            SELECT m.id, m.display_name, m.profile_photo_url,
                   (SELECT COUNT(DISTINCT p.id)
                    FROM photos p
                    JOIN photo_faces pf ON p.id = pf.photo_id
                    WHERE (pf.confirmed_member_id = m.id OR pf.matched_member_id = m.id)
                    AND (p.status = 'members_only' OR p.status = 'public')
                   ) as photo_count
            FROM members m
            HAVING photo_count > 0
            ORDER BY m.display_name
        ''').fetchall()

    result = []
    for member in members:
        result.append({
            'id': member['id'],
            'name': member['display_name'],
            'thumb': member['profile_photo_url'],
            'photoCount': member['photo_count']
        })

    return jsonify(result)


@gallery_bp.route('/api/activities.json')
def activities_list():
    """Get list of activity groups.

    Query params:
        - access: 'public' for public-only, 'members' for all approved (default)
    """
    access = request.args.get('access', 'members')

    if access == 'public':
        status_filter = "p.status = 'public'"
    else:
        status_filter = "(p.status = 'members_only' OR p.status = 'public')"

    with get_db() as conn:
        activities = conn.execute(f'''
            SELECT e.activity_group, COUNT(DISTINCT e.id) as event_count,
                   SUM((SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id
                        AND {status_filter})) as photo_count
            FROM events e
            WHERE e.activity_group IS NOT NULL
            GROUP BY e.activity_group
            HAVING photo_count > 0
            ORDER BY e.activity_group
        ''').fetchall()

    result = []
    for activity in activities:
        result.append({
            'id': activity['activity_group'],
            'name': activity['activity_group'],
            'eventCount': activity['event_count'],
            'photoCount': activity['photo_count']
        })

    return jsonify(result)


@gallery_bp.route('/api/config.json')
def config_api():
    """
    Get gallery configuration for client-side use.

    Returns configurable settings including:
    - Gallery display options (title, subtitle, thumbnail settings)
    - UI labels for localization
    - CDN library URLs for easy version upgrades
    - File upload settings (valid types, max size)
    """
    from app.gallery.config_manager import get_config

    config = get_config()

    # Return only client-relevant sections (exclude internal settings)
    client_config = {
        'gallery': config.get('gallery', {}),
        'labels': config.get('labels', {}),
        'libraries': config.get('libraries', {}),
        'upload': config.get('upload', {}),
        'presentation': config.get('presentation', {})
    }

    return jsonify(client_config)


@gallery_bp.route('/photos/<path:filepath>')
def serve_photo(filepath):
    """Serve photo files."""
    return send_from_directory(PHOTO_STORAGE_ROOT, filepath)


@gallery_bp.route('/upload', methods=['GET', 'POST'])
def upload_page():
    """Photo upload page and handler."""
    if request.method == 'GET':
        return render_template('gallery/upload.html')

    # Handle upload
    # TODO: Add authentication check
    member_id = request.form.get('member_id', 'anonymous')
    member_email = request.form.get('member_email', '')
    event_id = request.form.get('event_id')

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    from app.ingest.upload_handler import UploadHandler
    handler = UploadHandler(member_id, member_email)
    result = handler.process_upload(file, event_id)

    if result['success']:
        return jsonify({
            'success': True,
            'queue_id': result['queue_id'],
            'filename': result['filename']
        })
    else:
        return jsonify({
            'success': False,
            'error': result['error']
        }), 400


# =============================================================================
# Editorial Queue API - Public endpoints for WA-embedded admin interface
# These are accessible without Flask login since WA handles access control
# =============================================================================

@gallery_bp.route('/api/pending.json')
def pending_photos():
    """
    Get photos awaiting approval for the editorial queue.

    Query params:
        - filter: 'all', 'with_event', 'no_event', 'needs_faces'
        - page: page number (default 1)
        - per_page: items per page (default 20)
    """
    filter_type = request.args.get('filter', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    with get_db() as conn:
        # Build query based on filter
        base_query = '''
            SELECT p.id, p.thumb_path, p.display_path, p.original_filename,
                   p.submitted_at, p.taken_at, p.status,
                   p.event_id, p.event_match_confidence, p.event_match_method,
                   e.name as event_name, e.start_date as event_date,
                   m.display_name as submitter_name,
                   (SELECT COUNT(*) FROM photo_faces WHERE photo_id = p.id) as face_count,
                   (SELECT COUNT(*) FROM photo_faces WHERE photo_id = p.id
                    AND confirmed = FALSE AND matched_member_id IS NULL) as unidentified_count
            FROM photos p
            LEFT JOIN events e ON p.event_id = e.id
            LEFT JOIN members m ON p.submitter_member_id = m.id
            WHERE p.status = 'awaiting_approval'
        '''

        if filter_type == 'with_event':
            base_query += ' AND p.event_id IS NOT NULL'
        elif filter_type == 'no_event':
            base_query += ' AND p.event_id IS NULL'
        elif filter_type == 'needs_faces':
            base_query += ''' AND EXISTS (
                SELECT 1 FROM photo_faces pf
                WHERE pf.photo_id = p.id AND pf.confirmed = FALSE AND pf.matched_member_id IS NULL
            )'''

        base_query += ' ORDER BY p.submitted_at DESC LIMIT ? OFFSET ?'

        photos = conn.execute(base_query, (per_page, (page - 1) * per_page)).fetchall()

        # Get total count for pagination
        count_query = "SELECT COUNT(*) as c FROM photos WHERE status = 'awaiting_approval'"
        if filter_type == 'with_event':
            count_query += ' AND event_id IS NOT NULL'
        elif filter_type == 'no_event':
            count_query += ' AND event_id IS NULL'
        elif filter_type == 'needs_faces':
            count_query += ''' AND EXISTS (
                SELECT 1 FROM photo_faces pf
                WHERE pf.photo_id = photos.id AND pf.confirmed = FALSE AND pf.matched_member_id IS NULL
            )'''

        total = conn.execute(count_query).fetchone()['c']

    result = {
        'photos': [dict(p) for p in photos],
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    }

    return jsonify(result)


@gallery_bp.route('/api/queue-stats.json')
def queue_stats():
    """Get statistics for the editorial queue."""
    with get_db() as conn:
        stats = {}

        # Photo counts by status
        for status in ['awaiting_approval', 'members_only', 'public', 'do_not_post']:
            row = conn.execute(
                'SELECT COUNT(*) as count FROM photos WHERE status = ?',
                (status,)
            ).fetchone()
            stats[status] = row['count']

        # Unidentified faces
        unconfirmed = conn.execute('''
            SELECT COUNT(*) as count FROM photo_faces
            WHERE confirmed = FALSE AND matched_member_id IS NULL
        ''').fetchone()
        stats['unidentified_faces'] = unconfirmed['count']

        # Processing queue
        queue_stats = conn.execute('''
            SELECT status, COUNT(*) as count FROM processing_queue
            GROUP BY status
        ''').fetchall()
        stats['processing_queue'] = {row['status']: row['count'] for row in queue_stats}

    return jsonify(stats)


@gallery_bp.route('/api/photo/<photo_id>.json')
def photo_detail(photo_id):
    """Get full details for a single photo including faces."""
    with get_db() as conn:
        photo = conn.execute('''
            SELECT p.*, e.name as event_name, e.start_date as event_date,
                   m.display_name as submitter_name
            FROM photos p
            LEFT JOIN events e ON p.event_id = e.id
            LEFT JOIN members m ON p.submitter_member_id = m.id
            WHERE p.id = ?
        ''', (photo_id,)).fetchone()

        if not photo:
            return jsonify({'error': 'Photo not found'}), 404

        photo = dict(photo)

        # Get faces
        faces = conn.execute('''
            SELECT pf.*,
                   cm.display_name as confirmed_name, cm.profile_photo_url as confirmed_photo,
                   mm.display_name as matched_name, mm.profile_photo_url as matched_photo
            FROM photo_faces pf
            LEFT JOIN members cm ON pf.confirmed_member_id = cm.id
            LEFT JOIN members mm ON pf.matched_member_id = mm.id
            WHERE pf.photo_id = ?
            ORDER BY pf.box_left
        ''', (photo_id,)).fetchall()

        photo['faces'] = []
        for face in faces:
            face_dict = dict(face)
            # Parse candidates JSON
            if face_dict.get('candidates_json'):
                import json
                face_dict['candidates'] = json.loads(face_dict['candidates_json'])
            else:
                face_dict['candidates'] = []
            # Remove binary embedding from response
            if 'embedding' in face_dict:
                del face_dict['embedding']
            photo['faces'].append(face_dict)

        # Get prev/next for navigation
        prev_photo = conn.execute('''
            SELECT id FROM photos
            WHERE status = ? AND submitted_at < ?
            ORDER BY submitted_at DESC LIMIT 1
        ''', (photo['status'], photo['submitted_at'])).fetchone()

        next_photo = conn.execute('''
            SELECT id FROM photos
            WHERE status = ? AND submitted_at > ?
            ORDER BY submitted_at ASC LIMIT 1
        ''', (photo['status'], photo['submitted_at'])).fetchone()

        photo['prev_id'] = prev_photo['id'] if prev_photo else None
        photo['next_id'] = next_photo['id'] if next_photo else None

    return jsonify(photo)


@gallery_bp.route('/api/photo/<photo_id>/approve', methods=['POST'])
def approve_photo_api(photo_id):
    """Approve a photo (set status to members_only or public)."""
    from datetime import datetime

    data = request.get_json() or {}
    visibility = data.get('visibility', 'members_only')

    if visibility == 'public':
        status = 'public'
    else:
        status = 'members_only'

    with get_db() as conn:
        conn.execute('''
            UPDATE photos
            SET status = ?, reviewed_at = ?, updated_at = ?
            WHERE id = ?
        ''', (status, datetime.utcnow(), datetime.utcnow(), photo_id))

        # Update event photo count
        conn.execute('''
            UPDATE events SET photo_count = (
                SELECT COUNT(*) FROM photos
                WHERE event_id = events.id AND status IN ('members_only', 'public')
            )
        ''')

    return jsonify({'success': True, 'status': status})


@gallery_bp.route('/api/photo/<photo_id>/reject', methods=['POST'])
def reject_photo_api(photo_id):
    """Reject a photo (set status to do_not_post)."""
    from datetime import datetime

    data = request.get_json() or {}
    notes = data.get('notes', '')

    with get_db() as conn:
        conn.execute('''
            UPDATE photos
            SET status = 'do_not_post', review_notes = ?, reviewed_at = ?, updated_at = ?
            WHERE id = ?
        ''', (notes, datetime.utcnow(), datetime.utcnow(), photo_id))

    return jsonify({'success': True})


@gallery_bp.route('/api/photo/<photo_id>/event', methods=['POST'])
def update_photo_event_api(photo_id):
    """Update the event assignment for a photo."""
    from datetime import datetime

    data = request.get_json() or {}
    event_id = data.get('event_id')

    with get_db() as conn:
        conn.execute('''
            UPDATE photos
            SET event_id = ?, event_match_method = 'manual', updated_at = ?
            WHERE id = ?
        ''', (event_id if event_id else None, datetime.utcnow(), photo_id))

    return jsonify({'success': True})


@gallery_bp.route('/api/photo/<photo_id>/face', methods=['POST'])
def update_face_api(photo_id):
    """Update face identification."""
    data = request.get_json() or {}
    face_id = data.get('face_id')
    member_id = data.get('member_id')
    is_guest = data.get('is_guest', False)

    if not face_id:
        return jsonify({'success': False, 'error': 'Face ID required'}), 400

    from datetime import datetime

    with get_db() as conn:
        conn.execute('''
            UPDATE photo_faces
            SET confirmed = TRUE,
                confirmed_member_id = ?,
                confirmed_at = ?,
                is_guest = ?
            WHERE id = ? AND photo_id = ?
        ''', (member_id if not is_guest else None, datetime.utcnow(), is_guest, face_id, photo_id))

    return jsonify({'success': True})


@gallery_bp.route('/api/members/search')
def search_members_api():
    """Search members for face identification."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])

    with get_db() as conn:
        members = conn.execute('''
            SELECT id, display_name, email, profile_photo_url
            FROM members
            WHERE display_name LIKE ? OR email LIKE ?
            ORDER BY display_name
            LIMIT 20
        ''', (f'%{query}%', f'%{query}%')).fetchall()

    return jsonify([dict(m) for m in members])

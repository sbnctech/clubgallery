"""
SBNC Photo Gallery System - Admin Routes
Flask routes for the admin interface.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
import json
import logging

from app.database import (
    get_db, get_pending_photos, get_photo_with_faces,
    update_photo_status, confirm_face_identity
)
from app.config import PhotoStatus, PHOTO_STORAGE_ROOT
from app.processing.pipeline import process_queue, reprocess_photo
from app.processing.face_detector import save_confirmed_face_embedding

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', static_folder='static', template_folder='templates')


@admin_bp.route('/')
@login_required
def dashboard():
    """Admin dashboard with statistics (full version)."""
    with get_db() as conn:
        # Get counts by status
        stats = {}
        for status in ['awaiting_approval', 'members_only', 'public', 'do_not_post']:
            row = conn.execute(
                'SELECT COUNT(*) as count FROM photos WHERE status = ?',
                (status,)
            ).fetchone()
            stats[status] = row['count']

        # Get unconfirmed face count
        unconfirmed = conn.execute('''
            SELECT COUNT(*) as count FROM photo_faces
            WHERE confirmed = FALSE AND matched_member_id IS NULL
        ''').fetchone()
        stats['unidentified_faces'] = unconfirmed['count']

        # Get queue stats
        queue_stats = conn.execute('''
            SELECT status, COUNT(*) as count FROM processing_queue
            GROUP BY status
        ''').fetchall()
        stats['queue'] = {row['status']: row['count'] for row in queue_stats}

        # Recent activity
        recent = conn.execute('''
            SELECT p.id, p.thumb_path, p.submitted_at, m.display_name as submitter,
                   e.name as event_name, p.status
            FROM photos p
            LEFT JOIN members m ON p.submitter_member_id = m.id
            LEFT JOIN events e ON p.event_id = e.id
            ORDER BY p.submitted_at DESC
            LIMIT 10
        ''').fetchall()

    return render_template('admin/dashboard.html',
                           stats=stats,
                           recent_photos=[dict(r) for r in recent])


@admin_bp.route('/review')
@login_required
def reviewer_dashboard():
    """Enhanced reviewer dashboard with pre-processed info."""
    filter_type = request.args.get('filter', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 12

    with get_db() as conn:
        # Get stats
        stats = {}
        stats['awaiting_approval'] = conn.execute(
            "SELECT COUNT(*) as c FROM photos WHERE status = 'awaiting_approval'"
        ).fetchone()['c']

        stats['unidentified_faces'] = conn.execute('''
            SELECT COUNT(*) as c FROM photo_faces
            WHERE confirmed = FALSE AND matched_member_id IS NULL
        ''').fetchone()['c']

        # Build query based on filter
        base_query = '''
            SELECT p.*,
                   e.name as event_name,
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
        photos = [dict(p) for p in photos]

        # Get faces for each photo
        for photo in photos:
            faces = conn.execute('''
                SELECT pf.*,
                       cm.display_name as confirmed_name, cm.profile_photo_url as member_photo,
                       mm.display_name as matched_name
                FROM photo_faces pf
                LEFT JOIN members cm ON pf.confirmed_member_id = cm.id
                LEFT JOIN members mm ON pf.matched_member_id = mm.id
                WHERE pf.photo_id = ?
            ''', (photo['id'],)).fetchall()
            photo['faces'] = [dict(f) for f in faces]

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
        total_pages = (total + per_page - 1) // per_page

    return render_template('admin/reviewer_dashboard.html',
                           photos=photos,
                           stats=stats,
                           filter=filter_type,
                           page=page,
                           total_pages=total_pages)


@admin_bp.route('/photos')
@login_required
def photos_home():
    """Photo Editor landing page - for photo review volunteers."""
    with get_db() as conn:
        # Get counts by status
        stats = {}
        for status in ['awaiting_approval', 'members_only', 'public', 'do_not_post']:
            row = conn.execute(
                'SELECT COUNT(*) as count FROM photos WHERE status = ?',
                (status,)
            ).fetchone()
            stats[status] = row['count']

        # Get unconfirmed face count
        unconfirmed = conn.execute('''
            SELECT COUNT(*) as count FROM photo_faces
            WHERE confirmed = FALSE AND matched_member_id IS NULL
        ''').fetchone()
        stats['unidentified_faces'] = unconfirmed['count']

        # Get queue stats
        queue_stats = conn.execute('''
            SELECT status, COUNT(*) as count FROM processing_queue
            GROUP BY status
        ''').fetchall()
        stats['queue'] = {row['status']: row['count'] for row in queue_stats}

        # Recent photos
        recent = conn.execute('''
            SELECT p.id, p.thumb_path, p.status
            FROM photos p
            ORDER BY p.submitted_at DESC
            LIMIT 12
        ''').fetchall()

    return render_template('admin/photos_home.html',
                           stats=stats,
                           recent_photos=[dict(r) for r in recent])


@admin_bp.route('/site')
@login_required
def webmaster_home():
    """Webmaster landing page - for site configuration."""
    with get_db() as conn:
        # Get photo counts
        stats = {}
        for status in ['awaiting_approval', 'members_only', 'public', 'do_not_post']:
            row = conn.execute(
                'SELECT COUNT(*) as count FROM photos WHERE status = ?',
                (status,)
            ).fetchone()
            stats[status] = row['count']

        # Total photos
        total = conn.execute('SELECT COUNT(*) as count FROM photos').fetchone()
        stats['total'] = total['count']

        # Get queue stats
        queue_stats = conn.execute('''
            SELECT status, COUNT(*) as count FROM processing_queue
            GROUP BY status
        ''').fetchall()
        stats['queue'] = {row['status']: row['count'] for row in queue_stats}

    return render_template('admin/webmaster_home.html', stats=stats)


@admin_bp.route('/queue')
@login_required
def review_queue():
    """Photo review queue."""
    status = request.args.get('status', 'awaiting_approval')
    page = request.args.get('page', 1, type=int)
    per_page = 20

    with get_db() as conn:
        # Get total count
        total = conn.execute(
            'SELECT COUNT(*) as count FROM photos WHERE status = ?',
            (status,)
        ).fetchone()['count']

        # Get photos for this page
        photos = conn.execute('''
            SELECT p.*, e.name as event_name, m.display_name as submitter_name,
                   (SELECT COUNT(*) FROM photo_faces WHERE photo_id = p.id) as face_count,
                   (SELECT COUNT(*) FROM photo_faces WHERE photo_id = p.id AND confirmed = FALSE AND matched_member_id IS NULL) as unidentified_count
            FROM photos p
            LEFT JOIN events e ON p.event_id = e.id
            LEFT JOIN members m ON p.submitter_member_id = m.id
            WHERE p.status = ?
            ORDER BY p.submitted_at DESC
            LIMIT ? OFFSET ?
        ''', (status, per_page, (page - 1) * per_page)).fetchall()

    return render_template('admin/queue.html',
                           photos=[dict(p) for p in photos],
                           status=status,
                           page=page,
                           per_page=per_page,
                           total=total)


@admin_bp.route('/photo/<photo_id>')
@login_required
def photo_editor(photo_id):
    """Photo editor with face identification."""
    photo = get_photo_with_faces(photo_id)
    if not photo:
        flash('Photo not found', 'error')
        return redirect(url_for('admin.review_queue'))

    # Get event info
    event = None
    if photo.get('event_id'):
        with get_db() as conn:
            event = conn.execute(
                'SELECT * FROM events WHERE id = ?',
                (photo['event_id'],)
            ).fetchone()
            if event:
                event = dict(event)

    # Parse candidates JSON for each face
    for face in photo['faces']:
        if face.get('candidates_json'):
            face['candidates'] = json.loads(face['candidates_json'])
        else:
            face['candidates'] = []

    # Get navigation (prev/next in queue)
    with get_db() as conn:
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

    return render_template('admin/editor.html',
                           photo=photo,
                           event=event,
                           prev_id=prev_photo['id'] if prev_photo else None,
                           next_id=next_photo['id'] if next_photo else None)


@admin_bp.route('/photo/<photo_id>/approve', methods=['POST'])
@login_required
def approve_photo(photo_id):
    """Approve a photo."""
    visibility = request.form.get('visibility', 'members_only')

    if visibility == 'public':
        status = PhotoStatus.PUBLIC
    else:
        status = PhotoStatus.MEMBERS_ONLY

    update_photo_status(photo_id, status, reviewed_by=current_user.email)

    # Update event photo count
    with get_db() as conn:
        conn.execute('''
            UPDATE events SET photo_count = (
                SELECT COUNT(*) FROM photos
                WHERE event_id = events.id AND status IN ('members_only', 'public')
            )
        ''')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': status})

    flash('Photo approved', 'success')
    return redirect(url_for('admin.review_queue'))


@admin_bp.route('/photo/<photo_id>/reject', methods=['POST'])
@login_required
def reject_photo(photo_id):
    """Reject a photo."""
    notes = request.form.get('notes', '')
    update_photo_status(photo_id, PhotoStatus.DO_NOT_POST,
                        reviewed_by=current_user.email, notes=notes)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True})

    flash('Photo rejected', 'success')
    return redirect(url_for('admin.review_queue'))


@admin_bp.route('/photo/<photo_id>/face', methods=['POST'])
@login_required
def update_face(photo_id):
    """Update face identification."""
    face_id = request.form.get('face_id', type=int)
    member_id = request.form.get('member_id')
    is_guest = request.form.get('is_guest', 'false').lower() == 'true'

    if not face_id:
        return jsonify({'success': False, 'error': 'Face ID required'}), 400

    # Confirm the face
    confirm_face_identity(face_id, member_id if not is_guest else None,
                          confirmed_by=current_user.email, is_guest=is_guest)

    # If confirmed with a member, save the embedding for future recognition
    if member_id and not is_guest:
        save_confirmed_face_embedding(face_id, member_id)

    return jsonify({'success': True})


@admin_bp.route('/photo/<photo_id>/reprocess', methods=['POST'])
@login_required
def reprocess(photo_id):
    """Re-run face detection on a photo."""
    result = reprocess_photo(photo_id)
    return jsonify(result)


@admin_bp.route('/flash-process', methods=['POST'])
@login_required
def flash_process():
    """Trigger immediate queue processing."""
    result = process_queue(batch_size=20)
    return jsonify(result)


@admin_bp.route('/members/search')
@login_required
def search_members():
    """Search members for face identification."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])

    with get_db() as conn:
        members = conn.execute('''
            SELECT id, display_name, profile_photo_url
            FROM members
            WHERE display_name LIKE ? OR email LIKE ?
            LIMIT 20
        ''', (f'%{query}%', f'%{query}%')).fetchall()

    return jsonify([dict(m) for m in members])


@admin_bp.route('/events')
@login_required
def list_events():
    """List events with photo counts."""
    with get_db() as conn:
        events = conn.execute('''
            SELECT e.*, COUNT(p.id) as photo_count
            FROM events e
            LEFT JOIN photos p ON e.id = p.event_id AND p.status IN ('members_only', 'public')
            GROUP BY e.id
            ORDER BY e.start_date DESC
        ''').fetchall()

    return render_template('admin/events.html', events=[dict(e) for e in events])


@admin_bp.route('/photo/<photo_id>/event', methods=['POST'])
@login_required
def update_photo_event(photo_id):
    """Update the event assignment for a photo."""
    event_id = request.form.get('event_id')

    with get_db() as conn:
        conn.execute('''
            UPDATE photos
            SET event_id = ?, event_match_method = 'manual', updated_at = ?
            WHERE id = ?
        ''', (event_id if event_id else None, datetime.utcnow(), photo_id))

    return jsonify({'success': True})


@admin_bp.route('/photo/<photo_id>/delete', methods=['POST'])
@login_required
def delete_photo(photo_id):
    """Permanently delete a photo."""
    with get_db() as conn:
        # Get paths
        photo = conn.execute(
            'SELECT original_path, display_path, thumb_path FROM photos WHERE id = ?',
            (photo_id,)
        ).fetchone()

        if photo:
            # Delete files
            for path_key in ['original_path', 'display_path', 'thumb_path']:
                if photo[path_key]:
                    full_path = PHOTO_STORAGE_ROOT / photo[path_key]
                    if full_path.exists():
                        full_path.unlink()

            # Delete database records
            conn.execute('DELETE FROM photo_faces WHERE photo_id = ?', (photo_id,))
            conn.execute('DELETE FROM photo_tags WHERE photo_id = ?', (photo_id,))
            conn.execute('DELETE FROM photos WHERE id = ?', (photo_id,))

    return jsonify({'success': True})


@admin_bp.route('/bulk/approve', methods=['POST'])
@login_required
def bulk_approve():
    """Bulk approve photos."""
    photo_ids = request.form.getlist('photo_ids')
    visibility = request.form.get('visibility', 'members_only')

    status = PhotoStatus.PUBLIC if visibility == 'public' else PhotoStatus.MEMBERS_ONLY

    for photo_id in photo_ids:
        update_photo_status(photo_id, status, reviewed_by=current_user.email)

    return jsonify({'success': True, 'count': len(photo_ids)})


@admin_bp.route('/bulk/reject', methods=['POST'])
@login_required
def bulk_reject():
    """Bulk reject photos."""
    photo_ids = request.form.getlist('photo_ids')

    for photo_id in photo_ids:
        update_photo_status(photo_id, PhotoStatus.DO_NOT_POST, reviewed_by=current_user.email)

    return jsonify({'success': True, 'count': len(photo_ids)})


@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Gallery settings editor."""
    from app.gallery.config_manager import get_config, save_config

    if request.method == 'POST':
        config = get_config()

        # Update gallery settings
        config['gallery']['title'] = request.form.get('gallery_title', config['gallery']['title'])
        config['gallery']['subtitle'] = request.form.get('gallery_subtitle', config['gallery']['subtitle'])
        config['gallery']['thumbnailHeight'] = int(request.form.get('gallery_thumbnailHeight', 180))
        config['gallery']['maxRows'] = int(request.form.get('gallery_maxRows', 20))
        config['gallery']['gutterWidth'] = int(request.form.get('gallery_gutterWidth', 8))
        config['gallery']['gutterHeight'] = int(request.form.get('gallery_gutterHeight', 8))

        # Update labels
        config['labels']['findMember'] = request.form.get('labels_findMember', config['labels']['findMember'])
        config['labels']['activity'] = request.form.get('labels_activity', config['labels']['activity'])
        config['labels']['event'] = request.form.get('labels_event', config['labels']['event'])
        config['labels']['year'] = request.form.get('labels_year', config['labels']['year'])
        config['labels']['clear'] = request.form.get('labels_clear', config['labels']['clear'])
        config['labels']['loading'] = request.form.get('labels_loading', config['labels']['loading'])
        config['labels']['browseEvents'] = request.form.get('labels_browseEvents', config['labels']['browseEvents'])
        config['labels']['eventPhotos'] = request.form.get('labels_eventPhotos', config['labels']['eventPhotos'])
        config['labels']['memberPhotos'] = request.form.get('labels_memberPhotos', config['labels']['memberPhotos'])
        config['labels']['activityEvents'] = request.form.get('labels_activityEvents', config['labels']['activityEvents'])

        # Update upload settings
        config['upload']['maxFileSizeMB'] = int(request.form.get('upload_maxFileSizeMB', 20))

        # Update library URLs
        config['libraries']['jquery'] = request.form.get('libraries_jquery', config['libraries']['jquery'])
        config['libraries']['nanogallery2Js'] = request.form.get('libraries_nanogallery2Js', config['libraries']['nanogallery2Js'])
        config['libraries']['nanogallery2Css'] = request.form.get('libraries_nanogallery2Css', config['libraries']['nanogallery2Css'])
        config['libraries']['select2Js'] = request.form.get('libraries_select2Js', config['libraries']['select2Js'])
        config['libraries']['select2Css'] = request.form.get('libraries_select2Css', config['libraries']['select2Css'])

        # Update face recognition settings
        config['faceRecognition']['highConfidenceThreshold'] = float(request.form.get('faceRecognition_highConfidenceThreshold', 0.4))
        config['faceRecognition']['mediumConfidenceThreshold'] = float(request.form.get('faceRecognition_mediumConfidenceThreshold', 0.5))
        config['faceRecognition']['publicEventThreshold'] = float(request.form.get('faceRecognition_publicEventThreshold', 0.35))

        if save_config(config):
            flash('Settings saved successfully', 'success')
        else:
            flash('Error saving settings', 'error')

        return redirect(url_for('admin.settings'))

    config = get_config()
    return render_template('admin/settings.html', config=config)


@admin_bp.route('/settings/reset', methods=['POST'])
@login_required
def reset_settings():
    """Reset settings to defaults."""
    from app.gallery.config_manager import reset_config

    if reset_config():
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to reset config'})


@admin_bp.route('/presentation', methods=['GET', 'POST'])
@login_required
def presentation():
    """Gallery presentation editor - configure what members see."""
    from app.gallery.config_manager import get_config, save_config

    if request.method == 'POST':
        config = get_config()

        # Update filter visibility
        config['presentation']['filters']['showMemberSearch'] = 'filter_member' in request.form
        config['presentation']['filters']['showActivityFilter'] = 'filter_activity' in request.form
        config['presentation']['filters']['showEventFilter'] = 'filter_event' in request.form
        config['presentation']['filters']['showYearFilter'] = 'filter_year' in request.form

        # Update activity groups
        hidden_activities = []
        custom_names = {}
        for key in request.form:
            if key.startswith('activity_visible_'):
                pass  # Visible activities are checked
            elif key.startswith('activity_name_'):
                activity_id = key.replace('activity_name_', '')
                name = request.form[key].strip()
                if name:
                    custom_names[activity_id] = name

        # Find hidden activities (unchecked checkboxes)
        with get_db() as conn:
            all_activities = conn.execute('''
                SELECT DISTINCT activity_group FROM events
                WHERE activity_group IS NOT NULL
            ''').fetchall()
            for row in all_activities:
                activity_id = row['activity_group']
                if f'activity_visible_{activity_id}' not in request.form:
                    hidden_activities.append(activity_id)

        config['presentation']['activityGroups']['hidden'] = hidden_activities
        config['presentation']['activityGroups']['customNames'] = custom_names

        # Activity display order
        order_str = request.form.get('activity_order', '')
        if order_str:
            config['presentation']['activityGroups']['displayOrder'] = order_str.split(',')

        # Default view settings
        config['presentation']['defaultView']['activity'] = request.form.get('default_activity') or None
        config['presentation']['defaultView']['year'] = request.form.get('default_year') or None
        config['presentation']['defaultView']['recentMonths'] = int(request.form.get('recent_months', 0) or 0)

        # Header display
        config['presentation']['header']['show'] = 'show_header' in request.form
        config['presentation']['header']['showSubtitle'] = 'show_subtitle' in request.form

        # Featured events
        config['presentation']['featured']['showFeaturedSection'] = 'show_featured' in request.form
        pinned_str = request.form.get('pinned_events', '')
        config['presentation']['featured']['pinnedEvents'] = [e for e in pinned_str.split(',') if e]

        if save_config(config):
            flash('Presentation settings saved', 'success')
        else:
            flash('Error saving settings', 'error')

        return redirect(url_for('admin.presentation'))

    # GET request - load data for the form
    config = get_config()

    # Get activities with stats
    with get_db() as conn:
        activities = conn.execute('''
            SELECT e.activity_group as id, e.activity_group as name,
                   COUNT(DISTINCT e.id) as eventCount,
                   SUM((SELECT COUNT(*) FROM photos p WHERE p.event_id = e.id
                        AND (p.status = 'members_only' OR p.status = 'public'))) as photoCount
            FROM events e
            WHERE e.activity_group IS NOT NULL
            GROUP BY e.activity_group
            ORDER BY e.activity_group
        ''').fetchall()
        activities = [dict(a) for a in activities]

        # Get events for featured selection
        events = conn.execute('''
            SELECT id, name, start_date as date
            FROM events
            WHERE EXISTS (SELECT 1 FROM photos p WHERE p.event_id = events.id
                          AND (p.status = 'members_only' OR p.status = 'public'))
            ORDER BY start_date DESC
        ''').fetchall()
        events = [dict(e) for e in events]

        # Create events lookup by ID
        events_by_id = {e['id']: e for e in events}

        # Get unique years
        years = sorted(set(
            e['date'][:4] for e in events if e.get('date')
        ), reverse=True)

    # Sort activities by custom order if set
    order = config.get('presentation', {}).get('activityGroups', {}).get('displayOrder', [])
    if order:
        def sort_key(a):
            try:
                return order.index(a['id'])
            except ValueError:
                return len(order)
        activities.sort(key=sort_key)

    return render_template('admin/presentation.html',
                           config=config,
                           activities=activities,
                           events=events,
                           events_by_id=events_by_id,
                           years=years)


@admin_bp.route('/presentation/reset', methods=['POST'])
@login_required
def reset_presentation():
    """Reset presentation settings to defaults."""
    from app.gallery.config_manager import get_config, save_config, DEFAULT_CONFIG

    config = get_config()
    config['presentation'] = DEFAULT_CONFIG['presentation'].copy()

    if save_config(config):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to reset'})

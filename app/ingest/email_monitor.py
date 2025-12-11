"""
SBNC Photo Gallery System - Email Ingestion
Monitor photos@sbnewcomers.org for incoming photo submissions.
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr
import os
import uuid
from datetime import datetime
from pathlib import Path
import logging

from app.config import (
    IMAP_SERVER, IMAP_PORT, IMAP_USER, IMAP_PASSWORD,
    PHOTO_STORAGE_ROOT, SUPPORTED_IMAGE_EXTENSIONS
)
from app.database import get_db, get_member_by_email

logger = logging.getLogger(__name__)


class EmailMonitor:
    """Monitor IMAP mailbox for photo submissions."""

    def __init__(self):
        self.server = IMAP_SERVER
        self.port = IMAP_PORT
        self.user = IMAP_USER
        self.password = IMAP_PASSWORD
        self.connection = None
        self.inbox_folder = 'INBOX'
        self.processed_folder = 'Processed'
        self.rejected_folder = 'Rejected'

    def connect(self):
        """Connect to the IMAP server."""
        try:
            self.connection = imaplib.IMAP4_SSL(self.server, self.port)
            self.connection.login(self.user, self.password)
            logger.info(f"Connected to {self.server} as {self.user}")
            self._ensure_folders_exist()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            return False

    def _ensure_folders_exist(self):
        """Create processed/rejected folders if they don't exist."""
        for folder in [self.processed_folder, self.rejected_folder]:
            try:
                self.connection.create(folder)
            except:
                pass  # Folder already exists

    def disconnect(self):
        """Disconnect from the IMAP server."""
        if self.connection:
            try:
                self.connection.logout()
            except:
                pass
            self.connection = None

    def process_inbox(self):
        """Process all unread emails in the inbox."""
        if not self.connection:
            if not self.connect():
                return []

        results = []
        try:
            self.connection.select(self.inbox_folder)
            _, message_numbers = self.connection.search(None, 'UNSEEN')

            for num in message_numbers[0].split():
                if num:
                    result = self._process_email(num)
                    results.append(result)

        except Exception as e:
            logger.error(f"Error processing inbox: {e}")

        return results

    def _process_email(self, msg_num):
        """Process a single email message."""
        result = {
            'success': False,
            'msg_num': msg_num,
            'sender': None,
            'member': None,
            'photos': [],
            'errors': []
        }

        try:
            _, msg_data = self.connection.fetch(msg_num, '(RFC822)')
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

            # Extract sender info
            sender_name, sender_email = parseaddr(msg.get('From', ''))
            sender_email = sender_email.lower()
            result['sender'] = sender_email

            # Get email subject
            subject = decode_header(msg.get('Subject', ''))[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode('utf-8', errors='ignore')

            # Validate sender is an SBNC member
            member = get_member_by_email(sender_email)
            if not member:
                result['errors'].append(f"Sender {sender_email} is not an SBNC member")
                self._send_rejection_email(sender_email, "non_member")
                self._move_to_folder(msg_num, self.rejected_folder)
                return result

            result['member'] = member
            logger.info(f"Processing email from {member['display_name']} ({sender_email})")

            # Extract photo attachments
            photos_found = []
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue

                filename = part.get_filename()
                if not filename:
                    continue

                # Decode filename if needed
                if isinstance(filename, bytes):
                    filename = filename.decode('utf-8', errors='ignore')

                # Check if it's a supported image type
                ext = Path(filename).suffix.lower()
                if ext not in SUPPORTED_IMAGE_EXTENSIONS:
                    continue

                # Save the attachment
                photo_data = part.get_payload(decode=True)
                if photo_data:
                    saved_path = self._save_attachment(photo_data, filename, member['id'])
                    if saved_path:
                        # Check for duplicates
                        from app.processing.duplicate_detector import check_duplicate
                        is_duplicate, existing = check_duplicate(saved_path)
                        if is_duplicate:
                            # Remove the duplicate file
                            try:
                                Path(saved_path).unlink()
                            except:
                                pass
                            logger.info(f"Skipped duplicate from email: {filename}")
                            result['errors'].append(f"Duplicate: {filename}")
                            continue

                        photos_found.append({
                            'path': saved_path,
                            'original_filename': filename,
                            'size': len(photo_data)
                        })

            result['photos'] = photos_found

            if not photos_found:
                result['errors'].append("No valid photo attachments found")
                self._send_confirmation_email(sender_email, member['first_name'], 0)
            else:
                # Queue photos for processing
                self._queue_photos_for_processing(photos_found, member, sender_email)
                self._send_confirmation_email(sender_email, member['first_name'], len(photos_found))
                result['success'] = True

            # Move email to processed folder
            self._move_to_folder(msg_num, self.processed_folder)

        except Exception as e:
            logger.error(f"Error processing email {msg_num}: {e}")
            result['errors'].append(str(e))

        return result

    def _save_attachment(self, data, filename, member_id):
        """Save an email attachment to the upload queue directory."""
        try:
            # Create a unique filename
            ext = Path(filename).suffix.lower()
            unique_name = f"{uuid.uuid4()}{ext}"

            # Save to a queue directory
            queue_dir = PHOTO_STORAGE_ROOT / 'queue' / datetime.now().strftime('%Y/%m')
            queue_dir.mkdir(parents=True, exist_ok=True)

            file_path = queue_dir / unique_name
            with open(file_path, 'wb') as f:
                f.write(data)

            logger.info(f"Saved attachment: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"Failed to save attachment {filename}: {e}")
            return None

    def _queue_photos_for_processing(self, photos, member, sender_email):
        """Add photos to the processing queue."""
        with get_db() as conn:
            for photo in photos:
                conn.execute('''
                    INSERT INTO processing_queue
                    (photo_path, submitter_email, submitter_member_id, source, original_filename, status)
                    VALUES (?, ?, ?, 'email', ?, 'pending')
                ''', (photo['path'], sender_email, member['id'], photo['original_filename']))

    def _move_to_folder(self, msg_num, folder):
        """Move an email to a different folder."""
        try:
            self.connection.copy(msg_num, folder)
            self.connection.store(msg_num, '+FLAGS', '\\Deleted')
            self.connection.expunge()
        except Exception as e:
            logger.error(f"Failed to move message to {folder}: {e}")

    def _send_confirmation_email(self, to_email, first_name, photo_count):
        """Send a confirmation email to the submitter."""
        # TODO: Implement using smtplib
        if photo_count > 0:
            logger.info(f"Would send confirmation to {to_email}: {photo_count} photos received")
        else:
            logger.info(f"Would send notification to {to_email}: no photos found in submission")

    def _send_rejection_email(self, to_email, reason):
        """Send a rejection email for non-member submissions."""
        # TODO: Implement using smtplib
        logger.info(f"Would send rejection to {to_email}: {reason}")


def run_email_check():
    """Run a single check of the email inbox."""
    monitor = EmailMonitor()
    try:
        results = monitor.process_inbox()
        total_photos = sum(len(r['photos']) for r in results)
        successful = sum(1 for r in results if r['success'])
        logger.info(f"Processed {len(results)} emails, {successful} successful, {total_photos} photos queued")
        return results
    finally:
        monitor.disconnect()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_email_check()

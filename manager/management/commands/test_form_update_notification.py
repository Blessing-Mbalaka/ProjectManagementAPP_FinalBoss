"""
Management command to test form update notification system
Creates test papers/conferences and simulates form updates to trigger notifications
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from manager.models import Paper, Conference, ChangeLog
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test SMTP notification system for form updates on Papers and Conferences'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting notification system test...\n'))
        
        # Get or create test users
        lead_author = User.objects.first()
        if not lead_author:
            self.stdout.write(self.style.ERROR('[!] No users found in database'))
            return
        
        co_author = User.objects.filter(is_staff=False).first()
        if not co_author:
            co_author = lead_author
        
        self.stdout.write(f'Using lead author: {lead_author}')
        self.stdout.write(f'Using co-author: {co_author}\n')
        
        # Test 1: Paper Form Update Notification
        self.stdout.write(self.style.WARNING('Test 1: Paper Form Update Notification'))
        self.test_paper_notification(lead_author, co_author)
        
        # Test 2: Conference Form Update Notification
        self.stdout.write(self.style.WARNING('\nTest 2: Conference Form Update Notification'))
        self.test_conference_notification(lead_author, co_author)
        
        # Test 3: Verify ChangeLog Entries
        self.stdout.write(self.style.WARNING('\nTest 3: Verify ChangeLog Entries'))
        self.test_changelog_entries()
        
        self.stdout.write(self.style.SUCCESS('\n[OK] All tests completed!'))

    def test_paper_notification(self, lead_author, co_author):
        """Test notification on paper form update"""
        try:
            # Create test paper
            paper = Paper.objects.create(
                title='Test Paper for Notification',
                paper_type='journal',
                status='draft',
                lead_author_user=lead_author,
                abstract='Initial abstract',
            )
            paper.co_authors_users.add(co_author)
            self.stdout.write(f'  Created test paper: {paper.id}')
            
            # Simulate form update
            paper.title = 'Updated Test Paper Title'
            paper.abstract = 'Updated abstract with more details'
            paper._changed_by = lead_author
            paper.save()
            
            self.stdout.write(f'  [OK] Updated paper title and abstract')
            
            # Check ChangeLog entries
            changes = ChangeLog.get_recent_changes('paper', paper.id)
            if changes.exists():
                self.stdout.write(f'  [OK] {changes.count()} changelog entries created')
                for change in changes:
                    self.stdout.write(f'    - {change.field_label}: {change.old_value} -> {change.new_value}')
            else:
                self.stdout.write('  [WARN] No changelog entries found')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERR] Error: {str(e)}'))
            import traceback
            traceback.print_exc()

    def test_conference_notification(self, lead_author, co_author):
        """Test notification on conference form update"""
        try:
            # Create test conference
            conference = Conference.objects.create(
                conference_name='Test Conference for Notification',
                location='Test Location',
                lead_author_user=lead_author,
            )
            conference.co_authors_users.add(co_author)
            self.stdout.write(f'  Created test conference: {conference.id}')
            
            # Simulate form update
            conference.conference_name = 'Updated Test Conference Name'
            conference.location = 'Updated Location - New City'
            conference._changed_by = lead_author
            conference.save()
            
            self.stdout.write(f'  [OK] Updated conference name and location')
            
            # Check ChangeLog entries
            changes = ChangeLog.get_recent_changes('conference', conference.id)
            if changes.exists():
                self.stdout.write(f'  [OK] {changes.count()} changelog entries created')
                for change in changes:
                    self.stdout.write(f'    - {change.field_label}: {change.old_value} -> {change.new_value}')
            else:
                self.stdout.write('  [WARN] No changelog entries found')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERR] Error: {str(e)}'))
            import traceback
            traceback.print_exc()

    def test_changelog_entries(self):
        """Verify ChangeLog entries exist for both papers and conferences"""
        try:
            paper_changes = ChangeLog.objects.filter(content_type='paper').count()
            conference_changes = ChangeLog.objects.filter(content_type='conference').count()
            
            self.stdout.write(f'  Paper changelog entries: {paper_changes}')
            self.stdout.write(f'  Conference changelog entries: {conference_changes}')
            
            if paper_changes > 0 and conference_changes > 0:
                self.stdout.write(self.style.SUCCESS('  [OK] ChangeLog entries working correctly'))
            else:
                self.stdout.write(self.style.WARNING('  [WARN] Expected more changelog entries'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  [ERR] Error: {str(e)}'))

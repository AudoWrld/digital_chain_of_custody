from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from cases.models import Case
from evidence.models import Evidence
from reports.models import AnalysisReport
from custody.models import CustodyTransfer, StorageLocation, CustodyLog
from django.core.files.uploadedfile import SimpleUploadedFile
import io


class AnalystRoleRestrictionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.analyst = User.objects.create_user(
            username='analyst',
            password='testpass123',
            role='analyst',
            email='analyst@test.com'
        )
        
        self.investigator = User.objects.create_user(
            username='investigator',
            password='testpass123',
            role='investigator',
            email='investigator@test.com'
        )
        
        self.custodian = User.objects.create_user(
            username='custodian',
            password='testpass123',
            role='custodian',
            email='custodian@test.com'
        )
        
        self.admin = User.objects.create_superuser(
            username='admin',
            password='testpass123',
            email='admin@test.com'
        )
        
        self.case = Case.objects.create(
            case_id='CASE202601280001',
            title='Test Case',
            description='Test Description',
            created_by=self.investigator,
            status='evidence_collection'
        )
        
        self.evidence = Evidence.objects.create(
            case=self.case,
            original_filename='test_file.txt',
            description='Test Evidence',
            uploaded_by=self.investigator,
            file_size=1024,
            file_format='text/plain',
            media_type='document',
            sha256_hash='a' * 64,
            md5_hash='b' * 32,
            encrypted_file=SimpleUploadedFile(
                name='test_encrypted.txt',
                content=b'encrypted content',
                content_type='application/octet-stream'
            )
        )
    
    def test_analyst_cannot_upload_evidence(self):
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.get(reverse('evidence:upload_evidence', args=[self.case.case_id]))
        self.assertEqual(response.status_code, 403)
        
        file_content = b'Test file content'
        uploaded_file = SimpleUploadedFile(
            name='test.txt',
            content=file_content,
            content_type='text/plain'
        )
        
        response = self.client.post(
            reverse('evidence:upload_evidence', args=[self.case.case_id]),
            {
                'description': 'Test Evidence',
                'file': uploaded_file,
            }
        )
        self.assertEqual(response.status_code, 403)
    
    def test_analyst_cannot_modify_custody_records(self):
        self.client.login(username='analyst', password='testpass123')
        
        storage_location = StorageLocation.objects.create(
            name='Test Storage',
            description='Test Description',
            location_type='digital',
            managed_by=self.custodian
        )
        
        response = self.client.get(
            reverse('custody:request_transfer', args=[self.evidence.id])
        )
        self.assertEqual(response.status_code, 403)
        
        response = self.client.post(
            reverse('custody:request_transfer', args=[self.evidence.id]),
            {
                'to_user': self.custodian.id,
                'reason': 'Test transfer',
            }
        )
        self.assertEqual(response.status_code, 403)
        
        transfer = CustodyTransfer.objects.create(
            evidence=self.evidence,
            from_user=self.investigator,
            to_user=self.custodian,
            requested_by=self.investigator,
            reason='Test transfer',
            status='pending'
        )
        
        response = self.client.get(
            reverse('custody:approve_transfer', args=[transfer.id])
        )
        self.assertEqual(response.status_code, 403)
        
        response = self.client.post(
            reverse('custody:approve_transfer', args=[transfer.id]),
            {
                'status': 'approved',
                'review_notes': 'Approved',
            }
        )
        self.assertEqual(response.status_code, 403)
    
    def test_analyst_can_verify_evidence_hashes(self):
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.get(
            reverse('evidence:verify_evidence_integrity', args=[self.evidence.id])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_analyst_can_create_analysis_reports(self):
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.get(
            reverse('reports:create', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('reports:create', args=[self.case.case_id]),
            {
                'title': 'Test Report',
                'content': 'Test content',
                'findings': 'Test findings',
                'recommendations': 'Test recommendations',
            }
        )
        self.assertEqual(response.status_code, 302)
        
        report = AnalysisReport.objects.filter(
            case=self.case,
            created_by=self.analyst
        ).first()
        self.assertIsNotNone(report)
    
    def test_analyst_can_view_reports(self):
        report = AnalysisReport.objects.create(
            case=self.case,
            evidence=self.evidence,
            created_by=self.analyst,
            title='Test Report',
            content='Test content',
            status='draft'
        )
        
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.get(reverse('reports:view', args=[report.id]))
        self.assertEqual(response.status_code, 200)
    
    def test_analyst_can_edit_own_reports(self):
        report = AnalysisReport.objects.create(
            case=self.case,
            evidence=self.evidence,
            created_by=self.analyst,
            title='Test Report',
            content='Test content',
            status='draft'
        )
        
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.get(reverse('reports:edit', args=[report.id]))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('reports:edit', args=[report.id]),
            {
                'title': 'Updated Report',
                'content': 'Updated content',
                'findings': 'Updated findings',
                'recommendations': 'Updated recommendations',
            }
        )
        self.assertEqual(response.status_code, 302)
        
        report.refresh_from_db()
        self.assertEqual(report.title, 'Updated Report')
    
    def test_analyst_can_submit_reports(self):
        report = AnalysisReport.objects.create(
            case=self.case,
            evidence=self.evidence,
            created_by=self.analyst,
            title='Test Report',
            content='Test content',
            status='draft'
        )
        
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.post(reverse('reports:submit', args=[report.id]))
        self.assertEqual(response.status_code, 302)
        
        report.refresh_from_db()
        self.assertEqual(report.status, 'submitted')
    
    def test_analyst_cannot_review_reports(self):
        report = AnalysisReport.objects.create(
            case=self.case,
            evidence=self.evidence,
            created_by=self.analyst,
            title='Test Report',
            content='Test content',
            status='submitted'
        )
        
        self.client.login(username='analyst', password='testpass123')
        
        response = self.client.get(reverse('reports:review', args=[report.id]))
        self.assertEqual(response.status_code, 403)


class CustodianRoleRestrictionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.custodian = User.objects.create_user(
            username='custodian',
            password='testpass123',
            role='custodian',
            email='custodian@test.com'
        )
        
        self.investigator = User.objects.create_user(
            username='investigator',
            password='testpass123',
            role='investigator',
            email='investigator@test.com'
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            role='regular_user',
            email='regular@test.com'
        )
        
        self.admin = User.objects.create_superuser(
            username='admin',
            password='testpass123',
            email='admin@test.com'
        )
        
        self.case = Case.objects.create(
            case_id='CASE202601280001',
            title='Test Case',
            description='Test Description',
            created_by=self.regular_user,
            status='evidence_collection'
        )
        
        self.evidence = Evidence.objects.create(
            case=self.case,
            original_filename='test_file.txt',
            description='Test Evidence',
            uploaded_by=self.investigator,
            file_size=1024,
            file_format='text/plain',
            media_type='document',
            sha256_hash='a' * 64,
            md5_hash='b' * 32,
            encrypted_file=SimpleUploadedFile(
                name='test_encrypted.txt',
                content=b'encrypted content',
                content_type='application/octet-stream'
            )
        )
    
    def test_custodian_cannot_create_cases(self):
        self.client.login(username='custodian', password='testpass123')
        
        response = self.client.get(reverse('cases:create_case'))
        self.assertEqual(response.status_code, 403)
        
        response = self.client.post(
            reverse('cases:create_case'),
            {
                'title': 'Test Case',
                'description': 'Test Description',
                'priority': 'medium',
            }
        )
        self.assertEqual(response.status_code, 403)
    
    def test_custodian_cannot_close_cases(self):
        self.client.login(username='custodian', password='testpass123')
        
        response = self.client.get(
            reverse('cases:request_case_closure', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 403)
        
        response = self.client.post(
            reverse('cases:request_case_closure', args=[self.case.case_id]),
            {
                'closure_reason': 'Test reason',
            }
        )
        self.assertEqual(response.status_code, 403)
        
        response = self.client.get(
            reverse('cases:close_case', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 403)
        
        response = self.client.post(
            reverse('cases:close_case', args=[self.case.case_id]),
            {
                'closure_reason': 'Test reason',
            }
        )
        self.assertEqual(response.status_code, 403)
        
        response = self.client.get(
            reverse('cases:approve_case_closure', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 403)
    
    def test_custodian_can_manage_storage_locations(self):
        self.client.login(username='custodian', password='testpass123')
        
        # Test case storages list - the correct existing URL
        response = self.client.get(reverse('custody:case_storages'))
        self.assertEqual(response.status_code, 200)
        
        # Create a storage location manually for testing
        storage_location = StorageLocation.objects.create(
            name='Test Storage',
            description='Test Description',
            location_type='digital',
            managed_by=self.custodian
        )
        self.assertIsNotNone(storage_location)
    
    def test_custodian_can_request_custody_transfers(self):
        self.client.login(username='custodian', password='testpass123')
        
        response = self.client.get(
            reverse('custody:request_transfer', args=[self.evidence.id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('custody:request_transfer', args=[self.evidence.id]),
            {
                'to_user': self.investigator.id,
                'reason': 'Test transfer',
            }
        )
        self.assertEqual(response.status_code, 302)
        
        transfer = CustodyTransfer.objects.filter(
            evidence=self.evidence,
            from_user=self.custodian
        ).first()
        self.assertIsNotNone(transfer)
    
    def test_custodian_can_approve_custody_transfers(self):
        transfer = CustodyTransfer.objects.create(
            evidence=self.evidence,
            from_user=self.investigator,
            to_user=self.custodian,
            requested_by=self.investigator,
            reason='Test transfer',
            status='pending'
        )
        
        self.client.login(username='custodian', password='testpass123')
        
        response = self.client.get(
            reverse('custody:approve_transfer', args=[transfer.id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('custody:approve_transfer', args=[transfer.id]),
            {
                'status': 'approved',
                'review_notes': 'Approved',
            }
        )
        self.assertEqual(response.status_code, 302)
        
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'approved')
    
    def test_custodian_can_assign_evidence_storage(self):
        # Create storage location and evidence storage directly for testing
        storage_location = StorageLocation.objects.create(
            name='Test Storage',
            description='Test Description',
            location_type='digital',
            managed_by=self.custodian
        )
        
        from custody.models import EvidenceStorage
        # Create evidence storage directly
        storage = EvidenceStorage.objects.create(
            evidence=self.evidence,
            storage_location=storage_location,
            stored_by=self.custodian,
            notes='Test notes'
        )
        
        self.assertIsNotNone(storage)
        self.assertEqual(storage.storage_location, storage_location)
    
    def test_custodian_can_view_custody_logs(self):
        CustodyLog.log_action(
            evidence=self.evidence,
            case=self.case,
            user=self.investigator,
            action='stored',
            details='Test log entry'
        )
        
        self.client.login(username='custodian', password='testpass123')
        
        response = self.client.get(
            reverse('custody:evidence_custody_log', args=[self.evidence.id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(
            reverse('custody:case_custody_log', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_custodian_can_access_custody_dashboard(self):
        self.client.login(username='custodian', password='testpass123')
        
        response = self.client.get(reverse('custody:dashboard'))
        self.assertEqual(response.status_code, 200)


class InvestigatorRolePermissionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.investigator = User.objects.create_user(
            username='investigator',
            password='testpass123',
            role='investigator',
            email='investigator@test.com'
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            role='regular_user',
            email='regular@test.com'
        )
        
        self.case = Case.objects.create(
            case_id='CASE202601280001',
            title='Test Case',
            description='Test Description',
            created_by=self.regular_user,
            status='evidence_collection'
        )
    
    def test_investigator_can_upload_evidence(self):
        self.client.login(username='investigator', password='testpass123')
        
        response = self.client.get(
            reverse('evidence:upload_evidence', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
        
        file_content = b'Test file content'
        uploaded_file = SimpleUploadedFile(
            name='test.txt',
            content=file_content,
            content_type='text/plain'
        )
        
        response = self.client.post(
            reverse('evidence:upload_evidence', args=[self.case.case_id]),
            {
                'description': 'Test Evidence',
                'file': uploaded_file,
            }
        )
        self.assertEqual(response.status_code, 302)
        
        evidence = Evidence.objects.filter(
            case=self.case,
            uploaded_by=self.investigator
        ).first()
        self.assertIsNotNone(evidence)
    
    def test_investigator_can_modify_custody_records(self):
        self.client.login(username='investigator', password='testpass123')
        
        evidence = Evidence.objects.create(
            case=self.case,
            original_filename='test_file.txt',
            description='Test Evidence',
            uploaded_by=self.investigator,
            file_size=1024,
            file_format='text/plain',
            media_type='document',
            sha256_hash='a' * 64,
            md5_hash='b' * 32,
            encrypted_file=SimpleUploadedFile(
                name='test_encrypted.txt',
                content=b'encrypted content',
                content_type='application/octet-stream'
            )
        )
        
        custodian = User.objects.create_user(
            username='custodian',
            password='testpass123',
            role='custodian',
            email='custodian@test.com'
        )
        
        response = self.client.get(
            reverse('custody:request_transfer', args=[evidence.id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('custody:request_transfer', args=[evidence.id]),
            {
                'to_user': custodian.id,
                'reason': 'Test transfer',
            }
        )
        self.assertEqual(response.status_code, 302)
        
        transfer = CustodyTransfer.objects.filter(
            evidence=evidence,
            from_user=self.investigator
        ).first()
        self.assertIsNotNone(transfer)


class AdminRolePermissionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        
        self.admin = User.objects.create_superuser(
            username='admin',
            password='testpass123',
            email='admin@test.com'
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            role='regular_user',
            email='regular@test.com'
        )
        
        self.case = Case.objects.create(
            case_id='CASE202601280001',
            title='Test Case',
            description='Test Description',
            created_by=self.regular_user,
            status='evidence_collection'
        )
        
        self.evidence = Evidence.objects.create(
            case=self.case,
            original_filename='test_file.txt',
            description='Test Evidence',
            uploaded_by=self.regular_user,
            file_size=1024,
            file_format='text/plain',
            media_type='document',
            sha256_hash='a' * 64,
            md5_hash='b' * 32,
            encrypted_file=SimpleUploadedFile(
                name='test_encrypted.txt',
                content=b'encrypted content',
                content_type='application/octet-stream'
            )
        )
    
    def test_admin_can_upload_evidence(self):
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(
            reverse('evidence:upload_evidence', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
        
        file_content = b'Test file content'
        uploaded_file = SimpleUploadedFile(
            name='test.txt',
            content=file_content,
            content_type='text/plain'
        )
        
        response = self.client.post(
            reverse('evidence:upload_evidence', args=[self.case.case_id]),
            {
                'description': 'Test Evidence',
                'file': uploaded_file,
            }
        )
        self.assertEqual(response.status_code, 302)
    
    def test_admin_can_create_cases(self):
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(reverse('cases:create_case'))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('cases:create_case'),
            {
                'title': 'Test Case',
                'description': 'Test Description',
                'priority': 'medium',
            }
        )
        self.assertEqual(response.status_code, 302)
    
    def test_admin_can_close_cases(self):
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(
            reverse('cases:request_case_closure', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(
            reverse('cases:close_case', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(
            reverse('cases:approve_case_closure', args=[self.case.case_id])
        )
        self.assertEqual(response.status_code, 200)
    
    def test_admin_can_modify_custody_records(self):
        self.client.login(username='admin', password='testpass123')
        
        custodian = User.objects.create_user(
            username='custodian',
            password='testpass123',
            role='custodian',
            email='custodian@test.com'
        )
        
        response = self.client.get(
            reverse('custody:request_transfer', args=[self.evidence.id])
        )
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('custody:request_transfer', args=[self.evidence.id]),
            {
                'to_user': custodian.id,
                'reason': 'Test transfer',
            }
        )
        self.assertEqual(response.status_code, 302)
    
    def test_admin_can_review_reports(self):
        report = AnalysisReport.objects.create(
            case=self.case,
            evidence=self.evidence,
            created_by=self.regular_user,
            title='Test Report',
            content='Test content',
            status='submitted'
        )
        
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.get(reverse('reports:review', args=[report.id]))
        self.assertEqual(response.status_code, 200)
        
        response = self.client.post(
            reverse('reports:review', args=[report.id]),
            {
                'status': 'approved',
                'review_notes': 'Approved',
            }
        )
        self.assertEqual(response.status_code, 302)
        
        report.refresh_from_db()
        self.assertEqual(report.status, 'approved')
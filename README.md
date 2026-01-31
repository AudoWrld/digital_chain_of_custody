# Digital Chain of Custody

A Django-based web application that demonstrates the principles of a digital chain of custody.  
This project is developed as part of a Computer Security and Forensics course.

## Features
- Secure user authentication with role-based access.
- Case management dashboard for creating and managing cases.
- Evidence logging with metadata and cryptographic hash values.
- Tamper-evident custody transfer logs.
- Report generation for complete chain of custody records.
- Simulated evidence examples for academic and disciplinary cases.
- Evidence encryption and integrity verification.
- Analysis report generation for evidence examination.
- Comprehensive custody management system.

## Tech Stack
- Django (Python web framework)
- SQLite (default database, can be swapped for others)
- HTML, CSS, JavaScript (frontend)
- Cryptography library for evidence encryption

## Roles and Permissions

The system implements role-based access control with the following user roles:

### Regular User
- **Responsibilities**: Create new cases, submit cases for review
- **Permissions**: 
  - Create cases
  - View assigned cases
  - Cannot upload evidence or modify custody records

### Investigator
- **Responsibilities**: Upload evidence, register hashes, view custody logs
- **Permissions**:
  - Upload evidence to cases
  - View evidence details and custody logs
  - Request custody transfers
  - Cannot create or close cases

### Analyst
- **Responsibilities**: Analyze evidence, produce analysis reports, verify evidence hashes
- **Permissions**:
  - View evidence and case details
  - Verify evidence integrity (SHA-256 and MD5 hashes)
  - Create, edit, and submit analysis reports
  - View custody logs (read-only)
  - **Restrictions**:
    - Cannot upload original evidence
    - Cannot modify custody records
    - Cannot create or close cases

### Custodian
- **Responsibilities**: Manage evidence storage, transfer custody, maintain chain of custody
- **Permissions**:
  - Create and manage storage locations
  - Request and approve custody transfers
  - Assign evidence to storage locations
  - View custody logs
  - **Restrictions**:
    - Cannot create cases
    - Cannot close cases
    - Cannot upload evidence

### Auditor
- **Responsibilities**: Review custody logs, verify hashes, check assignment history
- **Permissions**:
  - View all custody logs
  - Verify evidence hashes
  - Review case audit trails
  - **Restrictions**:
    - Cannot modify any data
    - Cannot upload evidence
    - Cannot create or close cases

### Admin
- **Responsibilities**: Full system administration, case closure approval, report review
- **Permissions**:
  - All permissions from other roles
  - Create and close cases
  - Upload evidence
  - Modify custody records
  - Review and approve analysis reports
  - Manage all storage locations

## Evidence Handling

### Evidence Upload Rules
- Only investigators and admins can upload evidence
- Evidence is encrypted using AES-256 encryption with a case-specific key
- SHA-256 and MD5 hashes are computed before encryption for integrity verification
- Original evidence is immutable once uploaded
- Metadata is automatically extracted from uploaded files

### Evidence Encryption
- Each case has a unique encryption key
- Files are encrypted before storage
- Decryption is only available to authorized users
- Hashes are stored separately for verification

### Evidence Integrity Verification
- SHA-256 hash verification for file integrity
- MD5 hash for legacy compatibility
- Analysts and auditors can verify evidence integrity
- Any modification to evidence will be detected

## Chain of Custody

### Custody Log Fields
- Case ID
- Evidence ID
- User ID (who performed the action)
- Action (stored, retrieved, transferred, verified, archived, moved)
- Timestamp
- Details (additional information about the action)
- From/To storage locations
- To user (for transfers)

### Custody Actions
- **Stored**: Evidence is stored in a location
- **Retrieved**: Evidence is retrieved from storage
- **Transferred**: Custody is transferred to another user
- **Verified**: Evidence integrity is verified
- **Archived**: Evidence is archived for long-term storage
- **Moved**: Evidence is moved between storage locations

### Custody Logs
- Logs are append-only and protected from modification
- Every action on evidence is logged
- Logs include user, timestamp, and action details
- Custodians and auditors can view complete custody history

## Case Lifecycle

### Lifecycle Stages

#### Created
- **Assignee**: Regular User
- **Actions**:
  - Add case details
  - Submit for review

#### Evidence Collection
- **Assignee**: Investigator
- **Actions**:
  - Upload evidence
  - Register hashes
  - View custody logs

#### Analysis
- **Assignee**: Analyst
- **Actions**:
  - Analyze evidence
  - Add findings
  - Verify integrity
  - Create analysis reports

#### Review
- **Assignee**: Admin
- **Actions**:
  - Review reports
  - Verify custody
  - Approve closure

#### Closed
- **Assignee**: Admin
- **Actions**:
  - Lock case
  - Make case read-only

#### Archived
- **Assignee**: System
- **Actions**:
  - Long-term encrypted storage
  - Read-only access

### Case Transitions
- Only the current stage assignee or Admin can move a case forward
- Every transition is logged
- Reason for transition must be recorded
- Transitions maintain audit trail

### Case Closure
**Before closure**:
- Evidence hashes verified
- Reports finalized
- Custody logs reviewed

**After closure**:
- No modifications allowed
- Evidence remains encrypted
- Read-only access enforced

## Analysis Reports

### Report Features
- Analysts can create analysis reports for cases and evidence
- Reports include title, content, findings, and recommendations
- Reports go through a review workflow (draft → submitted → reviewed → approved)
- Admins review and approve submitted reports
- Reports are linked to cases and evidence

### Report Workflow
1. **Draft**: Analyst creates report
2. **Submitted**: Analyst submits for review
3. **Reviewed**: Admin reviews report
4. **Approved**: Report is approved and finalized

## Custody Management

### Storage Locations
- Custodians can create and manage storage locations
- Storage types: Physical, Digital, Cloud
- Capacity tracking for storage locations
- Evidence can be assigned to specific storage locations

### Custody Transfers
- Investigators and custodians can request custody transfers
- Transfers require approval
- All transfers are logged in custody logs
- Transfer history is maintained

### Custody Dashboard
- View pending transfers
- View transfer history
- Manage storage locations
- View custody logs

## Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/AudoWrld/digital_chain_of_custody.git
   cd digital_chain_of_custody
   ```

2. Create and activate a virtual env:
   ```bash
   python -m venv venv
    source venv/bin/activate  # On Windows use venv\Scripts\activate
    ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
    python manage.py runserver
    ```

## Testing
Run the test suite:
```bash
python manage.py test
```

Run specific test modules:
```bash
python manage.py test cases.tests.test_role_restrictions
python manage.py test evidence.tests
python manage.py test custody.tests
```

## Licence
This project is for academic purposes only and not intended for production use.

# Security Features Documentation

This document outlines the comprehensive security features implemented in the KYC/AML microservice, focusing on data encryption, privacy protection, and GDPR compliance.

## Field-Level Encryption

### Overview
The system implements field-level encryption for sensitive personally identifiable information (PII) to ensure data protection at rest.

### Encrypted Fields
- **User phone numbers** (`users.phone_number`)
- **Document numbers** (`documents.document_number`) - passport numbers, license numbers, etc.

### Implementation Details

#### Encryption Algorithm
- **Algorithm**: Fernet (symmetric encryption)
- **Key Derivation**: PBKDF2-HMAC-SHA256 with 100,000 iterations
- **Key Management**: Environment variable based with fallback to derived keys

#### Configuration
```bash
# Environment variables for encryption
ENCRYPTION_KEY=<base64-encoded-key>  # Optional: explicit encryption key
SECRET_KEY=<your-secret-key>         # Used for key derivation if ENCRYPTION_KEY not set
ENCRYPTION_KEY_ROTATION_ENABLED=false
ENCRYPTION_ALGORITHM=Fernet
```

#### Usage in Models
```python
from app.utils.encryption import EncryptedType

class User(BaseModel):
    phone_number = Column(EncryptedType(255), nullable=True)

class Document(BaseModel):
    document_number = Column(EncryptedType(255), nullable=True)
```

### Key Features
- **Transparent encryption/decryption**: Data is automatically encrypted when stored and decrypted when retrieved
- **Null value handling**: Properly handles None and empty string values
- **Unicode support**: Full support for international characters and emojis
- **Performance optimized**: Minimal overhead for encryption operations

## Data Masking in Logs

### Overview
Comprehensive data masking system prevents sensitive information from appearing in application logs.

### Masked Data Types
- **Email addresses**: `user@example.com` → `us***@example.com`
- **Phone numbers**: `555-123-4567` → `***-***-****`
- **Passport numbers**: `P123456789` → `XX******`
- **SSN numbers**: `123-45-6789` → `***-**-****`
- **Credit card numbers**: `4111-1111-1111-1111` → `****-****-****-****`

### Sensitive Field Detection
The system automatically masks fields with names containing:
- `password`, `token`, `secret`, `key`
- `phone_number`, `document_number`
- `passport_number`, `ssn`, `social_security_number`
- `credit_card`, `card_number`, `cvv`, `pin`

### Implementation
```python
from app.utils.logging import get_logger, mask_sensitive_data

logger = get_logger(__name__)

# Data is automatically masked in logs
logger.info("User data", user_data={
    "email": "user@example.com",      # Will be masked
    "phone": "555-123-4567",          # Will be masked
    "name": "John Doe"                # Will not be masked
})
```

### Configuration
Data masking is automatically enabled in the logging pipeline through the `mask_processor` in structlog configuration.

## GDPR Compliance Features

### Overview
Comprehensive GDPR compliance implementation providing users with full control over their personal data.

### Available Operations

#### 1. Data Export (Right to Access)
Users can export all their personal data in a structured format.

**Endpoints:**
- `GET /api/v1/gdpr/export/me` - Export own data
- `GET /api/v1/gdpr/export/{user_id}` - Export user data (admin only)

**Export includes:**
- User profile information
- KYC verification history
- Document metadata (without actual files)
- Webhook event history
- Processing timestamps and status

#### 2. Data Deletion (Right to Erasure)
Users can request deletion of their personal data with two options:

**Soft Delete (Default):**
- Anonymizes personal data but retains records for audit purposes
- Replaces sensitive fields with anonymized values
- Maintains referential integrity

**Hard Delete (Admin only):**
- Completely removes all user data from the system
- Cascades through all related records
- Irreversible operation

**Endpoints:**
- `DELETE /api/v1/gdpr/delete/me` - Delete own data (soft delete only)
- `DELETE /api/v1/gdpr/delete/{user_id}?soft_delete=true/false` - Delete user data (admin only)

#### 3. Data Processing Information (Right to Information)
Provides detailed information about how personal data is processed.

**Endpoints:**
- `GET /api/v1/gdpr/processing-info/me` - Get own processing info
- `GET /api/v1/gdpr/processing-info/{user_id}` - Get user processing info (admin only)

**Information includes:**
- Data categories collected
- Processing purposes and legal basis
- Retention periods
- Third-party data sharing details
- User rights and how to exercise them

### Data Categories and Processing

#### Personal Data
- **Purpose**: User identification and account management
- **Legal Basis**: Contract performance
- **Retention**: As long as account is active + 7 years

#### KYC Data
- **Purpose**: Identity verification and regulatory compliance
- **Legal Basis**: Legal obligation (AML/KYC regulations)
- **Retention**: 5 years after account closure

#### Technical Data
- **Purpose**: Service provision and security
- **Legal Basis**: Legitimate interest
- **Retention**: 2 years

### Implementation Example
```python
from app.services.gdpr_service import GDPRService

# Export user data
gdpr_service = GDPRService(db)
export_data = await gdpr_service.export_user_data(user_id)

# Delete user data (soft delete)
deletion_summary = await gdpr_service.delete_user_data(user_id, soft_delete=True)

# Get processing information
processing_info = await gdpr_service.get_data_processing_info(user_id)
```

## Security Testing

### Test Coverage
Comprehensive test suite covering all security features:

#### Encryption Tests
- **Unit tests**: `tests/unit/test_utils/test_encryption.py`
- **Integration tests**: `tests/integration/test_encryption_models.py`
- **Coverage**: Encryption/decryption, key rotation, performance, edge cases

#### Data Masking Tests
- **Unit tests**: `tests/unit/test_utils/test_logging_masking.py`
- **Coverage**: Pattern matching, field detection, nested data structures

#### GDPR Tests
- **Unit tests**: `tests/unit/test_services/test_gdpr_service.py`
- **Integration tests**: `tests/integration/test_gdpr_api.py`
- **Coverage**: Data export, deletion, anonymization, access controls

### Running Security Tests
```bash
# Run all security-related tests
pytest tests/unit/test_utils/test_encryption.py -v
pytest tests/unit/test_utils/test_logging_masking.py -v
pytest tests/unit/test_services/test_gdpr_service.py -v
pytest tests/integration/test_gdpr_api.py -v
pytest tests/integration/test_encryption_models.py -v

# Run with coverage
pytest --cov=app.utils.encryption --cov=app.utils.logging --cov=app.services.gdpr_service
```

## Security Best Practices

### Key Management
1. **Use dedicated encryption keys** in production environments
2. **Rotate encryption keys** regularly (when `ENCRYPTION_KEY_ROTATION_ENABLED=true`)
3. **Store keys securely** using environment variables or key management services
4. **Never commit keys** to version control

### Data Handling
1. **Minimize data collection** - only collect necessary PII
2. **Encrypt sensitive data** at rest using field-level encryption
3. **Mask sensitive data** in logs and error messages
4. **Implement data retention policies** according to GDPR requirements

### Access Control
1. **Role-based access control** for GDPR operations
2. **Users can only access their own data** unless they are administrators
3. **Audit all data access** and modifications
4. **Implement proper authentication** for all endpoints

### Compliance
1. **Document data processing** activities and legal basis
2. **Implement user rights** (access, rectification, erasure, portability)
3. **Maintain audit trails** for all data operations
4. **Regular security assessments** and penetration testing

## Monitoring and Alerting

### Security Events
The system logs security-related events for monitoring:

```python
from app.utils.logging import log_security_event

# Log security events
log_security_event(
    event_type="data_export_requested",
    user_id=user_id,
    ip_address=request.client.host,
    details={"export_type": "gdpr_full_export"}
)
```

### Metrics to Monitor
- Failed encryption/decryption attempts
- GDPR data export requests
- Data deletion requests
- Unauthorized access attempts
- Sensitive data exposure in logs

## Migration and Deployment

### Database Migration
When deploying encryption features:

1. **Run the encryption migration**:
   ```bash
   alembic upgrade head
   ```

2. **Verify encryption is working**:
   ```bash
   # Test encryption in development
   python -c "from app.utils.encryption import field_encryption; print(field_encryption.encrypt('test'))"
   ```

### Environment Setup
```bash
# Production environment variables
export ENCRYPTION_KEY="<base64-encoded-32-byte-key>"
export SECRET_KEY="<strong-secret-key>"
export LOG_LEVEL="INFO"
export LOG_FORMAT="json"
```

### Health Checks
The system includes health checks for security features:
- Encryption/decryption functionality
- Database connectivity for GDPR operations
- Log masking processor status

## Troubleshooting

### Common Issues

#### Encryption Errors
- **Symptom**: `InvalidToken` errors during decryption
- **Cause**: Key mismatch or corrupted data
- **Solution**: Verify `ENCRYPTION_KEY` and `SECRET_KEY` configuration

#### GDPR Export Failures
- **Symptom**: Export returns incomplete data
- **Cause**: Missing relationships or permissions
- **Solution**: Check database relationships and user permissions

#### Log Masking Not Working
- **Symptom**: Sensitive data appears in logs
- **Cause**: Masking processor not configured
- **Solution**: Verify logging configuration includes `mask_processor`

### Debug Mode
Enable debug logging for security features:
```bash
export LOG_LEVEL="DEBUG"
export ENCRYPTION_DEBUG="true"
```

## Compliance Checklist

- [ ] Field-level encryption implemented for all PII
- [ ] Data masking active in all log outputs
- [ ] GDPR data export functionality tested
- [ ] GDPR data deletion functionality tested
- [ ] User consent mechanisms implemented
- [ ] Data retention policies configured
- [ ] Security tests passing
- [ ] Audit logging enabled
- [ ] Key management procedures documented
- [ ] Incident response plan prepared
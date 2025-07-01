# CLAUDE.md

This file serves as the "constitution" for AI behavior when working with the WireGuard Gateway codebase. It provides comprehensive guidance for development, testing, deployment, and maintenance tasks.

## Purpose & Placement

- **Primary AI Guidance**: This file serves as the "constitution" for AI behavior when working with this WireGuard Gateway codebase
- **Scope**: Covers development, testing, deployment, and maintenance tasks
- **Audience**: AI assistants working on this specific Flask/WireGuard project
- **Placement**: Root directory alongside README.md for maximum visibility
- **Relationship**: Complements README.md (user-focused) with AI-specific guidance
- **Company Context**: YairTech specializes in business automation, custom CRM development, AI integration, and dashboards

## Common Commands

**Development:**
```bash
python run.py                    # Run Flask app directly
flask run                        # Run with Flask CLI
pip install -r requirements.txt  # Install dependencies
```

**Testing and Quality:**
```bash
pytest                           # Run all tests
pytest --cov                     # Run tests with coverage
black .                          # Format code with Black
flake8 .                         # Lint code with Flake8
```

**Git Workflow:**
```bash
git checkout -b feature/your-feature-name    # Create feature branch
git checkout -b bugfix/issue-description     # Create bugfix branch
git checkout -b hotfix/critical-fix          # Create hotfix branch
git add . && git commit -m "feat: add new feature"  # Stage and commit
git push origin feature/your-feature-name    # Push to remote
git pull origin develop                        # Sync with develop branch
```

**System Operations:**
```bash
sudo ./install.sh                # Full system installation
sudo ./install.sh --skip-pip     # Skip Python package installation
sudo ./install.sh --skip-dependencies  # Skip system dependencies
systemctl status wireguard-gateway     # Check service status
systemctl restart wireguard-gateway    # Restart service
```

**CRITICAL DEPLOYMENT NOTE:**
- **Production app runs from `/opt/wireguard-gateway/`** - NOT the development directory
- **Changes are only applied** when you run `sudo ./install.sh` (copies files to `/opt/`)
- **DO NOT** run `systemctl restart wireguard-gateway` to test changes - it won't see your changes
- **ALWAYS** run `sudo ./install.sh --skip-dependencies` to deploy code changes
- **Development directory** is for editing only, **`/opt/` directory** is where the live service runs

**Database Operations:**
- All database operations are handled automatically by the Flask app using SQLAlchemy
- No manual database commands needed
- Tables created automatically on app startup

**Virtual Environment:**
- **IMPORTANT**: Use `env/` directory (non-standard location)
- Activate with: `source env/bin/activate`

## Core Files & Directories

**Entry Points:**
- `run.py` - Flask application entry point (simple 6-line file)
- `install.sh` - Comprehensive system installation script (318 lines)

**Application Core:**
- `app/__init__.py` - Flask app factory with comprehensive initialization
- `app/routes/main.py` - **CRITICAL**: 1006 lines, needs refactoring into smaller modules
- `app/routes/auth.py` - Authentication routes (141 lines)

**Business Logic Layer:**
- `app/services/` - 13 service modules for WireGuard operations:
  - `wireguard.py` - Core WireGuard operations and config validation
  - `config_storage.py` - Client config storage and metadata management
  - `iptables_manager.py` - NAT/forwarding rules management
  - `wireguard_monitor.py` - Connection monitoring and status tracking
  - `auto_reconnect.py` - Automatic reconnection on DNS changes
  - `dns_resolver.py` - DNS monitoring for DDNS scenarios
  - `connectivity_test.py` - Network connectivity testing
  - `email_service.py` - Email alerting system
  - `pending_configs.py` - Temporary storage for invalid configs
  - `status_poller.py` - System status monitoring
  - `route_command_generator.py` - Router command generation
  - `ip_forwarding.py` - IP forwarding management
  - `reboot_service.py` - System reboot functionality

**Data Layer:**
- `app/models/` - SQLAlchemy models (User, Client, EmailSettings, AlertHistory)
- `app/database.py` - SQLAlchemy database instance

**Configuration & Runtime:**
- `requirements.txt` - Python dependencies (18 packages)
- `instance/` - Runtime data directory (configs, database, logs)
- `app/forms.py` - Flask-WTF form definitions

**Templates & Frontend:**
- `app/templates/` - Jinja2 templates with Bootstrap 5 UI
- `app/templates/base.html` - Base template (356 lines)
- `app/templates/clients.html` - Main clients interface (473 lines)

**Testing:**
- `tests/conftest.py` - Pytest configuration and fixtures
- `tests/services/` - Unit tests for all service modules

**System Integration:**
- `logs/` - Application logs directory
- `env/` - Virtual environment (non-standard location)

## Code Style Guidelines

**Python Standards:**
- Follow PEP 8 compliance
- Use Black for code formatting (`black .`)
- Use Flake8 for linting (`flake8 .`)
- Maximum line length: 88 characters (Black default)

**Flask Patterns:**
- Use blueprint-based routing (already implemented)
- Keep routes thin - delegate business logic to services
- Use app factory pattern (already implemented)
- Use service layer pattern for business logic

**File Organization:**
- Keep routes focused and under 200 lines (main.py needs refactoring)
- Business logic belongs in `app/services/`
- Models should be simple data containers
- Use descriptive names, avoid abbreviations in service names

**Documentation:**
- Docstrings for all public methods, especially in services
- Use type hints where appropriate
- Comment complex business logic, especially system integration code

**Error Handling:**
- Comprehensive try-catch blocks for system operations
- Return tuples (success, error_message) from service methods
- Log errors appropriately with context

## Testing Instructions

**Framework Setup:**
- Use Pytest as primary testing framework
- Coverage reporting with pytest-cov
- Fixtures defined in `tests/conftest.py`

**Test Structure:**
- Each service has corresponding test file in `tests/services/`
- Use temporary databases and instance directories
- Mock subprocess calls and system operations

**Running Tests:**
```bash
pytest                           # Run all tests
pytest --cov                     # Run with coverage
pytest tests/services/           # Run only service tests
pytest -v                        # Verbose output
```

**Test Coverage:**
- Aim for >80% coverage
- Focus on service layer coverage
- Test error conditions and edge cases
- Mock external system dependencies

**Integration Testing:**
- Test WireGuard operations with mocked system commands
- Test database operations with temporary databases
- Test authentication flows

## Repo Etiquette

**Critical Issues to Address:**
- **`app/routes/main.py` (1006 lines)** - Needs refactoring into smaller modules
- **`check_users.py`** - Empty file, should be removed or implemented
- **`REMEBER.txt`** - Incomplete development todos need attention

**Code Organization:**
- Follow the established service layer pattern
- Avoid adding new routes to main.py without refactoring
- Keep services focused and avoid duplication
- Use template inheritance effectively

**Git Workflow:**
- Follow branching strategy outlined in README.md
- Create feature branches from `develop`
- Keep commits focused and well-described
- Update documentation when adding new features

**File Management:**
- Remove empty or unused files
- Keep dependencies minimal in requirements.txt
- Update CLAUDE.md when adding new patterns or conventions

## Company Workflow & GitHub Practices

**YairTech Development Culture:**
- **Business-First Approach**: All code changes must solve real business problems
- **Efficiency Focus**: Prioritize solutions that reduce admin time and improve processes
- **Live Service Priority**: All live services must remain online and healthy at all times
- **Quality Over Speed**: Thorough testing and review before deployment
- **Documentation**: Clear documentation for maintainability and knowledge transfer

### Branching Strategy

**Branch Naming Conventions:**
```bash
feature/user-management-system     # New features
bugfix/vpn-connection-timeout      # Bug fixes
hotfix/security-patch-urgent       # Critical fixes
refactor/main-routes-split         # Code refactoring
docs/api-documentation-update      # Documentation updates
```

**Branch Workflow:**
- **`main`**: Production-ready code only
- **`develop`**: Integration branch for features
- **`feature/*`**: Feature development branches
- **`bugfix/*`**: Bug fix branches
- **`hotfix/*`**: Critical production fixes

**Branch Lifecycle:**
1. Create feature branch from `develop`
2. Develop and test locally
3. Push to remote and create draft PR
4. Request review when ready
5. Merge to `develop` after approval
6. Merge `develop` to `main` for releases

### Pull Request Process

**Required Reviewers:**
- **Code Owners**: @yairtech/code-owners (Yair and senior developers)
- **Security Review**: Required for system-level changes
- **Business Logic Review**: Required for new features affecting live services

**PR Template Usage:**
```markdown
## Description
Brief description of changes and business impact

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] No live service impact

## Business Impact
How does this change benefit the business or users?

## Related Issues
Closes #123, References #456
```

**PR States:**
- **Draft PRs**: For work-in-progress, no review required
- **Ready for Review**: All tests pass, ready for code review
- **Changes Requested**: Address reviewer feedback
- **Approved**: Ready for merge

**Merge Requirements:**
- All CI checks must pass
- At least one code owner approval
- No merge conflicts
- Documentation updated if needed

### Commit Message Guidelines

**Conventional Commits Format:**
```bash
feat: add user authentication system
fix: resolve VPN connection timeout issue
docs: update API documentation
refactor: split main routes into modules
test: add unit tests for email service
chore: update dependencies
```

**Commit Structure:**
```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New features
- `fix`: Bug fixes
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Issue References:**
- Always reference issue numbers: `Closes #123` or `Fixes #456`
- Use keywords: Closes, Fixes, Resolves, References

### Continuous Integration

**CI Pipeline (GitHub Actions):**
```yaml
# .github/workflows/ci.yml
name: CI Pipeline
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      - name: Run linting
        run: |
          black --check .
          flake8 .
      - name: Run tests
        run: |
          pytest --cov
      - name: Security scan
        run: |
          bandit -r app/
```

**CI Checks:**
- **Code Formatting**: Black formatting check
- **Linting**: Flake8 style and error checking
- **Unit Tests**: Pytest with coverage reporting
- **Security Scan**: Bandit security vulnerability scanning
- **Integration Tests**: End-to-end testing for critical paths

**Interpreting CI Failures:**
- **Formatting Failures**: Run `black .` locally and commit
- **Linting Failures**: Fix style issues reported by flake8
- **Test Failures**: Check test output and fix failing tests
- **Security Issues**: Address security vulnerabilities before merge
- **Coverage Drops**: Add tests for new code paths

### Code Review Etiquette

**Reviewer Responsibilities:**
- **Response Time**: Respond within 24 hours during business hours
- **Thorough Review**: Check code quality, security, and business logic
- **Constructive Feedback**: Provide specific, actionable suggestions
- **Approval Criteria**: Ensure code meets YairTech standards

**Author Responsibilities:**
- **Address Feedback**: Respond to all review comments
- **Test Changes**: Verify fixes work as expected
- **Update PR**: Push changes and update PR description
- **Request Re-review**: When ready for another review

**Review Guidelines:**
- **Code Quality**: Is the code readable and maintainable?
- **Security**: Are there any security vulnerabilities?
- **Performance**: Will this impact live service performance?
- **Business Logic**: Does this solve the intended business problem?
- **Testing**: Are there adequate tests for the changes?

**Conflict Resolution:**
- **Technical Disagreements**: Discuss in PR comments, escalate if needed
- **Business Logic**: Consult with product owner or Yair
- **Timeline Conflicts**: Prioritize based on business impact
- **Merge Conflicts**: Resolve locally and push updated branch

### Release & Deployment

**Version Management:**
- **Semantic Versioning**: MAJOR.MINOR.PATCH (e.g., 1.2.3)
- **Version Bumps**: Update version in `__init__.py` or `setup.py`
- **Changelog**: Maintain CHANGELOG.md with release notes

**Release Process:**
1. **Feature Freeze**: Stop merging features to `develop`
2. **Testing**: Run full test suite and integration tests
3. **Version Bump**: Update version number and changelog
4. **Tag Release**: Create git tag with version number
5. **Deploy**: Deploy to staging environment first
6. **Production**: Deploy to production after staging validation

**Deployment Strategy:**
- **Blue-Green Deployment**: Zero-downtime deployments
- **Rollback Plan**: Quick rollback to previous version if issues arise
- **Health Checks**: Monitor service health during deployment
- **Gradual Rollout**: Deploy to subset of users first if applicable

**Post-Deployment:**
- **Monitoring**: Watch logs and metrics for 30 minutes
- **Health Checks**: Verify all services are responding
- **User Feedback**: Monitor for any user-reported issues
- **Documentation**: Update deployment documentation if needed

**Emergency Procedures:**
- **Hotfix Process**: Create hotfix branch from `main`
- **Rollback**: Revert to previous stable version immediately
- **Communication**: Notify team and stakeholders of issues
- **Root Cause Analysis**: Document what went wrong and how to prevent it

### YairTech-Specific Considerations

**Business Automation Focus:**
- All features should reduce manual work or improve efficiency
- Consider impact on existing business processes
- Document business benefits in PR descriptions
- Test with real business scenarios

**Live Service Management:**
- **Uptime Priority**: Never compromise live service availability
- **Monitoring**: Use existing monitoring tools (see case studies at [yairtech.co.uk/case-studies](https://www.yairtech.co.uk/case-studies))
- **Backup Procedures**: Always have rollback plans
- **Communication**: Keep stakeholders informed of changes

**Quality Standards:**
- **Code Coverage**: Maintain >80% test coverage
- **Performance**: No significant performance regressions
- **Security**: Regular security reviews for system-level changes
- **Documentation**: Keep documentation up-to-date

**Cross-Project Integration:**
- Consider impact on other YairTech projects
- Follow established patterns from successful projects
- Reference relevant case studies and documentation
- Coordinate with team on shared dependencies

## Dev Environment

**Virtual Environment:**
- **CRITICAL**: Use `env/` directory (not standard `venv/`)
- Activate with: `source env/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

**Python Requirements:**
- Python 3.8+ compatibility required
- See `requirements.txt` for exact package versions
- Key dependencies: Flask 3.0.0, SQLAlchemy 2.0.40, pytest 8.0.2

**System Requirements:**
- Ubuntu/Debian-based system
- Root/sudo access required for WireGuard operations
- WireGuard tools and iptables installed

**Database:**
- SQLite for development (automatic initialization)
- Database file created in instance directory
- Tables created automatically on app startup

**Logging:**
- Rotating file handler in `logs/` directory
- Debug logging in development mode
- Structured logging for production

## Known Gotchas

**System Integration:**
- **Sudo Requirements**: Most WireGuard operations require sudo privileges
- **Complex Permissions**: Install script sets up complex file permissions
- **System Commands**: Heavy reliance on subprocess for system operations
- **Background Tasks**: Monitoring uses threading, not Celery

**Configuration Validation:**
- **AllowedIPs Restriction**: Cannot be `0.0.0.0/0` - forces specific subnets
- **Pending Configs**: Invalid configs stored temporarily for user correction
- **Config Validation**: Strict validation with detailed error messages

**Architecture Quirks:**
- **Multiple Monitoring Systems**: Overlapping functionality between services
- **File-Based Storage**: Configs stored in files alongside database metadata
- **Service Dependencies**: Complex interdependencies between services

**Development Issues:**
- **Large main.py**: 1006 lines needs refactoring
- **Empty Files**: check_users.py should be addressed
- **Incomplete Documentation**: REMEBER.txt has incomplete todos

**Performance Considerations:**
- Background monitoring runs every 30 seconds
- File I/O operations for config storage
- Database queries for status updates

## Security & Secrets

**Authentication System:**
- Flask-Login for session management
- Password hashing with Werkzeug
- Default credentials: admin/admin123 (forced change on first login)
- Rate limiting on sensitive endpoints

**Input Validation:**
- Strict WireGuard config validation
- File upload size limits (10KB max)
- File type validation (.conf files only)
- SQL injection prevention via SQLAlchemy

**System Security:**
- Controlled sudo execution via specific commands
- Restricted file permissions on config files
- User isolation (wireguard user for system operations)

**Environment Variables:**
- Use .env file for sensitive configuration
- SECRET_KEY for Flask sessions
- DATABASE_URL for database connection
- LOG_PATH for logging configuration

**Network Security:**
- Rate limiting on API endpoints
- Input sanitization for all user inputs
- Secure file handling for config uploads

## Token Efficiency

**Code Organization:**
- **Refactor main.py**: Split 1006-line file into focused modules
- **Service Separation**: Keep services focused and avoid duplication
- **Template Inheritance**: Use base template effectively
- **Configuration**: Use environment variables for flexibility

**Documentation Strategy:**
- Keep README.md user-focused
- Use CLAUDE.md for AI-specific guidance
- Prefer self-documenting code over excessive comments
- Update documentation when patterns change

**Development Practices:**
- Remove empty or unused files promptly
- Keep dependencies minimal and version-pinned
- Use type hints for better code understanding
- Implement proper error handling without verbose logging

**File Management:**
- Regular cleanup of temporary files
- Proper .gitignore patterns for generated files
- Minimal configuration files
- Efficient test organization

## Architecture Overview

This is a **Python Flask web application** for managing WireGuard VPN tunnels with system integration for NAT rules and monitoring.

### Backend Architecture (Flask)
- **Flask app factory pattern**: Main app created in `app/__init__.py` with blueprints
- **SQLAlchemy ORM**: Database models in `app/models/` (User, EmailSettings, AlertHistory, Client)
- **Blueprint-based routing**: Routes split between `app/routes/main.py` (main functionality) and `app/routes/auth.py` (authentication)
- **Service layer pattern**: Business logic in `app/services/` modules for WireGuard, networking, monitoring, etc.

### Key Services Architecture
- **WireGuardService** (`app/services/wireguard.py`): Core WireGuard config validation and operations
- **ConfigStorageService** (`app/services/config_storage.py`): Manages client configs and metadata storage
- **IptablesManager** (`app/services/iptables_manager.py`): Handles NAT/forwarding rules
- **WireGuardMonitor** (`app/services/wireguard_monitor.py`): Connection monitoring and alerting
- **AutoReconnectService** (`app/services/auto_reconnect.py`): Automatic reconnection on DNS changes
- **DNSResolver** (`app/services/dns_resolver.py`): DNS monitoring for DDNS scenarios

### Frontend Architecture
- **Server-rendered Jinja2 templates** in `app/templates/`
- **Bootstrap 5** CSS framework with custom CSS in base template
- **jQuery/JavaScript** for AJAX interactions and dynamic UI updates
- **Responsive design** with mobile-friendly navigation

### System Integration
- **Linux system calls**: Uses `subprocess` to execute `wg-quick`, `iptables`, and other system commands with `sudo`
- **File system operations**: Stores WireGuard configs in instance directory (`./instance/configs/`)
- **Background monitoring**: Task scheduler (`app/tasks.py`) runs connection monitoring

### Security Architecture
- **Flask-Login**: Session-based authentication with mandatory password changes
- **Rate limiting**: Built-in decorator for endpoint protection
- **Sudo integration**: Controlled system command execution for WireGuard operations
- **Input validation**: Strict validation of WireGuard configs and network subnets

### Data Flow
1. **Config Upload**: User uploads .conf → WireGuardService validates → ConfigStorageService stores
2. **Client Activation**: User activates → `wg-quick up` → IptablesManager sets NAT rules
3. **Monitoring**: WireGuardMonitor checks handshakes → EmailService sends alerts → AutoReconnectService handles failures

## Important Implementation Notes

- **Config validation**: AllowedIPs cannot be `0.0.0.0/0` - forces users to specify actual subnets
- **Pending configs**: Invalid configs with `0.0.0.0/0` are stored temporarily for user correction
- **Sudo requirements**: Most WireGuard operations require sudo privileges
- **Interface naming**: WireGuard interface names derived from config filenames
- **Database migrations**: Uses SQLAlchemy with `db.create_all()` for table creation
- **Background tasks**: Monitoring runs in daemon threads, not using Celery
- **File permissions**: Complex permission setup handled by install script
- **Service dependencies**: Multiple services have interdependencies that need careful management
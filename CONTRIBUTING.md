# Contributing to WireGuard Gateway UI

Thank you for your interest in contributing to WireGuard Gateway UI! This document provides guidelines and workflows for contributing.

## Development Workflow

1. Fork the repository
2. Create a feature branch from `develop`
   ```bash
   git checkout develop
   git checkout -b feature/your-feature-name
   ```

3. Set up your development environment:
   ```bash
   # Application setup
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

4. Make your changes
   - Write clear, concise commit messages
   - Include tests for new features
   - Update documentation as needed
   - Follow the templates structure in templates/
   - Keep JavaScript modular and minimal

5. Test your changes
   ```bash
   # Run tests
   pytest
   ```

6. Push your changes and create a pull request
   ```bash
   git push origin feature/your-feature-name
   ```

## Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update the docs/ with any new documentation
3. The PR must pass all tests
4. The PR must be reviewed by at least one maintainer

## Code Style

- Python: Follow PEP 8 guidelines
- HTML/CSS: Follow BEM naming convention
- JavaScript: Keep it simple and modular
- Use meaningful variable and function names
- Comment complex logic
- Keep functions small and focused

## Template Structure
- Base templates should extend from `base.html`
- Use template blocks appropriately
- Keep JavaScript minimal and in separate files
- Use Flask's url_for() for links
- Follow Jinja2 best practices

## Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

## Questions or Problems?

Feel free to open an issue for any questions or problems you encounter. 
# Contributing to Telegram Account Manager Bot

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Git
- MongoDB (local or cloud)
- Telegram API credentials

### Development Setup
1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/MeherMankar/TeleGuard.git
   cd telegram-account-manager
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install dependencies:
   ```bash
   pip install -r config/requirements.txt
   ```
5. Copy environment configuration:
   ```bash
   cp config/.env.example config/.env
   ```
6. Configure your `.env` file with test credentials

## 📝 Development Guidelines

### Code Style
- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions small and focused

### Security Considerations
- Never commit session files or API credentials
- Use environment variables for sensitive data
- Encrypt all stored session data
- Follow the principle of least privilege

### Testing
- Write tests for new features
- Ensure all tests pass before submitting PR
- Test with multiple account scenarios
- Verify OTP protection functionality

## 🔄 Pull Request Process

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Test thoroughly
4. Commit with clear messages:
   ```bash
   git commit -m "feat: add new profile management feature"
   ```
5. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
6. Create a Pull Request

### PR Requirements
- Clear description of changes
- Reference any related issues
- Include tests for new functionality
- Update documentation if needed
- Ensure CI passes

## 🐛 Bug Reports

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output
- Configuration details (without sensitive data)

## 💡 Feature Requests

For new features:
- Check existing issues first
- Describe the use case
- Explain the expected behavior
- Consider security implications
- Discuss implementation approach

## 📚 Documentation

- Update README.md for user-facing changes
- Add inline code documentation
- Update API documentation
- Include examples for new features

## 🔒 Security

- Report security vulnerabilities privately
- Don't include sensitive data in issues
- Follow responsible disclosure practices
- Test security features thoroughly

## 📋 Code Review Checklist

Before submitting:
- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No sensitive data is exposed
- [ ] Security implications are considered
- [ ] Performance impact is minimal

## 🏷️ Commit Message Format

Use conventional commits:
- `feat:` new features
- `fix:` bug fixes
- `docs:` documentation changes
- `style:` formatting changes
- `refactor:` code refactoring
- `test:` adding tests
- `chore:` maintenance tasks

## 📞 Getting Help

- Check existing documentation
- Search existing issues
- Ask questions in discussions
- Join our community channels

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

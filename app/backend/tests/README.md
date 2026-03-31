# Tests - NewsAnalyzer Backend

Comprehensive test suite for the NewsAnalyzer backend, including unit and integration tests for the LangChain ecosystem integration.

## 📁 Structure

```
tests/
├── unit/                          # Unit tests (fast, no I/O)
│   ├── test_insight_memory.py   # LangMem cache tests
│   └── test_insights_graph.py   # LangGraph workflow tests
├── integration/                   # Integration tests (with external services)
└── fixtures/                      # Test fixtures and mocks
    └── mock_providers.py         # Mock LLM providers
```

## 🚀 Running Tests

### Install Test Dependencies

```bash
cd app/backend
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/unit/test_insight_memory.py
pytest tests/unit/test_insights_graph.py
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage Report

```bash
pytest --cov=adapters --cov=core --cov-report=html --cov-report=term
```

Coverage report will be generated in `htmlcov/index.html`.

### Run Only Unit Tests

```bash
pytest -m unit
```

### Run Only Integration Tests

```bash
pytest -m integration
```

## 📊 Test Categories

### Unit Tests

Fast tests that don't require external services:
- **test_insight_memory.py**: LangMem cache operations, statistics, TTL, eviction
- **test_insights_graph.py**: LangGraph nodes, validation, retry logic, workflow

### Integration Tests

Tests that may require external services (PostgreSQL, Qdrant, LLMs):
- *Coming soon*: End-to-end workflow tests with real providers

## 🎯 Test Coverage

Current test coverage:

| Component | Coverage | Tests |
|-----------|----------|-------|
| **InsightMemory** | ~90% | 15 tests |
| **InsightsGraph** | ~85% | 12 tests |
| **Mock Providers** | 100% | N/A (fixtures) |

## 🧪 Writing New Tests

### Unit Test Template

```python
import pytest
from your_module import YourClass

class TestYourFeature:
    """Test description."""
    
    @pytest.fixture
    def instance(self):
        """Create instance for testing."""
        return YourClass()
    
    @pytest.mark.asyncio
    async def test_feature(self, instance):
        """Test specific feature."""
        result = await instance.method()
        assert result == expected
```

### Using Mock Providers

```python
from tests.fixtures.mock_providers import MockExtractionProvider

# Create mock with custom responses
mock_provider = MockExtractionProvider(
    responses={
        'keyword': 'Custom response when prompt contains keyword'
    }
)

# Use in test
result = await mock_provider.generate(request)
assert result.text == 'Custom response...'
```

## 🐛 Debugging Tests

### Run Single Test

```python
pytest tests/unit/test_insight_memory.py::TestInsightMemoryBasic::test_store_and_get -v
```

### Run with Print Statements

```bash
pytest -s  # Don't capture stdout
```

### Run with PDB Debugger

```bash
pytest --pdb  # Drop into debugger on failure
```

## 📝 Test Naming Conventions

- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Fixtures: descriptive names (e.g., `memory`, `mock_provider`)

## ✅ Pre-commit Checklist

Before committing code:

1. **Run all tests**: `pytest`
2. **Check coverage**: `pytest --cov`
3. **Verify no warnings**: `pytest --strict-warnings`
4. **Format code**: `black .` (if using black)
5. **Lint code**: `ruff check .` (if using ruff)

## 📚 References

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [LangGraph Testing Guide](https://langchain-ai.github.io/langgraph/testing/)

## 🎓 Test Philosophy

### What to Test

✅ **DO test**:
- Business logic (domain services, validation)
- State transitions (LangGraph nodes)
- Edge cases (empty inputs, max retries, TTL expiration)
- Error handling (rate limits, timeouts, validation failures)
- Cache operations (hit/miss, eviction, statistics)

❌ **DON'T test**:
- External library internals (LangChain, LangGraph)
- Simple getters/setters
- Trivial pass-through functions

### Test Principles

1. **Fast**: Unit tests should complete in milliseconds
2. **Isolated**: No dependencies on external services
3. **Repeatable**: Same result every time
4. **Self-validating**: Pass/fail without human inspection
5. **Timely**: Written before or with production code

## 🔧 Troubleshooting

### ModuleNotFoundError

```bash
# Ensure you're in the backend directory
cd app/backend

# Install in editable mode
pip install -e .
```

### AsyncIO Deprecation Warnings

Update `pytest-asyncio` to latest version:

```bash
pip install --upgrade pytest-asyncio
```

### Import Errors

Ensure `PYTHONPATH` includes backend directory:

```bash
export PYTHONPATH=/path/to/news-analyzer/app/backend:$PYTHONPATH
pytest
```

## 📈 Continuous Integration

Tests run automatically on:
- Every commit (via pre-commit hook - future)
- Every pull request (via GitHub Actions - future)
- Nightly builds (full test suite including integration - future)

---

**Last Updated**: 2026-03-31  
**Test Framework**: pytest 7.4+  
**Coverage Target**: >80%

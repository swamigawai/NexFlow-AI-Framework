import pytest
import os
import sys

# Add project root to sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_html():
    return """
    <html>
        <body>
            <h1>Test Title</h1>
            <p class="description">Test Description</p>
            <ul>
                <li class="item">Item 1</li>
                <li class="item">Item 2</li>
            </ul>
        </body>
    </html>
    """

@pytest.fixture
def sample_selectors():
    return {
        "title": "h1",
        "desc": ".description",
        "items": ".item"
    }

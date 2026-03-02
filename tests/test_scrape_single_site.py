import pytest
import requests
from unittest.mock import patch, MagicMock
from execution.scrape_single_site import Scraper
from execution.utils.validators import ValidationError, validate_url

# --------
# Fixtures
# --------

@pytest.fixture
def scraper():
    return Scraper(timeout=5, use_random_agent=False)

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
        "items": ".item",
        "missing": ".non-existent"
    }

# --------
# Parsing Tests (8 tests)
# --------
def test_parse_html_single_element(scraper, mock_html, sample_selectors):
    results = scraper.parse_html(mock_html, sample_selectors)
    assert results["title"] == "Test Title"

def test_parse_html_multiple_elements(scraper, mock_html, sample_selectors):
    results = scraper.parse_html(mock_html, sample_selectors)
    assert len(results["items"]) == 2
    assert "Item 1" in results["items"]

def test_parse_html_missing_element(scraper, mock_html, sample_selectors):
    results = scraper.parse_html(mock_html, sample_selectors)
    assert results["missing"] is None

def test_parse_html_invalid_selectors(scraper, mock_html):
    with pytest.raises(ValidationError):
        scraper.parse_html(mock_html, {"invalid": 123})

def test_parse_html_empty_selectors(scraper, mock_html):
    with pytest.raises(ValidationError):
        scraper.parse_html(mock_html, {})

def test_parse_html_malformed_html(scraper, sample_selectors):
    # BeautifulSoup should handle malformed HTML gracefully with lxml
    html = "<h1   Test Title</h1 >"
    results = scraper.parse_html(html, {"title": "h1"})
    assert results["title"] == "" # or similar, but shouldn't raise exception

def test_parse_html_empty_html(scraper, sample_selectors):
    results = scraper.parse_html("", sample_selectors)
    assert all(value is None for value in results.values())

def test_parse_html_complex_selector(scraper):
    html = "<div class='container'><span id='target'>Found</span></div>"
    res = scraper.parse_html(html, {"target": "div.container span#target"})
    assert res["target"] == "Found"

# --------
# Fetching Tests (6 tests)
# --------
@patch("requests.Session.get")
def test_fetch_page_success(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Success"
    mock_get.return_value = mock_response
    assert scraper.fetch_page("https://example.com") == "Success"

@patch("requests.Session.get")
def test_fetch_page_http_error(mock_get, scraper):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
    mock_get.return_value = mock_response
    with pytest.raises(requests.exceptions.HTTPError):
        # We also need to patch exponential_backoff if we don't want it to retry, or let it retry 3 times fast 
        scraper.fetch_page("https://example.com")

@patch("requests.Session.get")
def test_fetch_page_timeout(mock_get, scraper):
    mock_get.side_effect = requests.exceptions.Timeout("Timeout")
    with pytest.raises(requests.exceptions.Timeout):
        scraper.fetch_page("https://example.com")

@patch("requests.Session.get")
def test_fetch_page_connection_error(mock_get, scraper):
    mock_get.side_effect = requests.exceptions.ConnectionError("Connection Refused")
    with pytest.raises(requests.exceptions.ConnectionError):
        scraper.fetch_page("https://example.com")

def test_fetch_page_invalid_url(scraper):
    with pytest.raises(ValidationError):
        scraper.fetch_page("not-a-url")

def test_fetch_page_wrong_scheme(scraper):
    with pytest.raises(ValidationError):
        scraper.fetch_page("ftp://example.com")

# --------
# Integration / Edge Case Tests (7 tests)
# --------
def test_scraper_init_timeout():
    scraper = Scraper(timeout=10)
    assert scraper.timeout == 10

def test_scraper_init_user_agent():
    scraper = Scraper(use_random_agent=True)
    assert "User-Agent" in scraper.session.headers

@patch("execution.scrape_single_site.Scraper.fetch_page")
@patch("execution.scrape_single_site.Scraper.parse_html")
@patch("execution.scrape_single_site.Scraper._save_output")
def test_run_success(mock_save, mock_parse, mock_fetch, scraper):
    mock_fetch.return_value = "<html></html>"
    mock_parse.return_value = {"title": "Test"}
    
    result = scraper.run("https://example.com", {"title": "h1"}, "out.json")
    
    assert result == {"title": "Test"}
    mock_fetch.assert_called_once_with("https://example.com")
    mock_parse.assert_called_once_with("<html></html>", {"title": "h1"})
    mock_save.assert_called_once_with({"title": "Test"}, "out.json")

@patch("execution.scrape_single_site.Scraper.fetch_page")
def test_run_fetch_failure(mock_fetch, scraper):
    mock_fetch.side_effect = requests.exceptions.ConnectionError()
    with pytest.raises(requests.exceptions.ConnectionError):
        scraper.run("https://example.com", {"title": "h1"}, "out.json")

@patch("execution.scrape_single_site.Scraper.fetch_page")
@patch("execution.scrape_single_site.Scraper.parse_html")
def test_run_parse_failure(mock_parse, mock_fetch, scraper):
    mock_fetch.return_value = "<html></html>"
    mock_parse.side_effect = ValidationError("Bad selector")
    with pytest.raises(ValidationError):
        scraper.run("https://example.com", {"invalid": 123}, "out.json")

@patch("os.makedirs")
@patch("os.replace")
@patch("builtins.open")
def test_save_output(mock_open, mock_replace, mock_makedirs, scraper):
    # Given
    data = {"test": 123}
    out_path = "some/dir/results.json"
    
    # When
    scraper._save_output(data, out_path)
    
    # Then
    mock_makedirs.assert_called_with("some/dir", exist_ok=True)
    mock_open.assert_called_with("some/dir/results.json.tmp", "w", encoding="utf-8")
    mock_replace.assert_called_with("some/dir/results.json.tmp", out_path)

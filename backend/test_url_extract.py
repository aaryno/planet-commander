from app.services.url_extractor import URLExtractor
from app.services.url_classifier import URLClassifier

# Test URL extraction from text
test_text = """
Check out this job: https://hello.planet.com/code/api/v4/jobs/39314506/artifacts
And this MR: https://hello.planet.com/code/wx/wx/-/merge_requests/1274
JIRA ticket: https://hello.planet.com/jira/browse/COMPUTE-2297
Google doc: https://docs.google.com/document/d/1234abcd/edit
"""

urls = URLExtractor.extract_urls(test_text)
print(f"Found {len(urls)} URLs:\n")

classifier = URLClassifier()
for url in urls:
    result = classifier.classify(url)
    print(f"URL: {url}")
    print(f"  Type: {result['type'].value}")
    print(f"  Components: {result['components']}")
    print()

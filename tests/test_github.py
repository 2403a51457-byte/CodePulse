import unittest
from modules.github_integration import validate_github_url

class GitHubValidationTests(unittest.TestCase):
    def test_normalizes_https_github_url(self):
        self.assertEqual(validate_github_url('https://github.com/example/project'), 'https://github.com/example/project.git')
        self.assertEqual(validate_github_url('https://github.com/example/project.git'), 'https://github.com/example/project.git')

    def test_rejects_non_github_or_non_https_urls(self):
        for url in ['http://github.com/example/project', 'https://evil.example/example/project', 'https://github.com/example']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_github_url(url)

if __name__ == '__main__':
    unittest.main()

from django.test import SimpleTestCase


class AcademicStaticTests(SimpleTestCase):
    def test_live_entry_uses_live_app_and_academic_presentation(self):
        response = self.client.get('/')
        html = b''.join(response.streaming_content).decode()
        self.assertIn('academic-ui.js', html)
        self.assertIn('backend-adapter.js', html)
        self.assertNotIn('design/uiux-b-prototype/core.js', html)
        self.assertNotIn('design/uiux-b-prototype/app.js', html)

    def test_academic_assets_are_available(self):
        for path in ['academic-pages.js', 'academic-pages.css', 'academic-ui.js', 'academic-ui.css', 'academic-messages.js',
                     'design/uiux-b-prototype/assets/association-logo.png',
                     'design/uiux-b-prototype/assets/campus-watercolor-v1.png']:
            with self.subTest(path=path):
                response = self.client.get('/' + path)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(b''.join(response.streaming_content))

    def test_prototype_runtime_and_private_paths_are_not_served(self):
        for path in ['design/uiux-b-prototype/index.html', 'design/uiux-b-prototype/core.js',
                     '.env.local', '.data/private-access/access-credentials.json',
                     'design/uiux-b-prototype/assets/../../../backend/config/settings.py']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/' + path).status_code, 404)

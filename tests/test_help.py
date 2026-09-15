"""The in-application help library."""
from __future__ import annotations

import re

from django.test import TestCase
from django.urls import reverse

from apps.help import library
from tests.factories import make_user
from tests.test_accounts import make_installer

PASSWORD = "Str0ng-Pass!23"


class LibraryLoadingTests(TestCase):
    def test_sections_and_topics_load(self):
        sections = library.load()
        self.assertGreaterEqual(len(sections), 10)
        self.assertGreaterEqual(len(library.all_topics()), 50)

    def test_every_topic_has_a_title_and_summary(self):
        missing = [
            f"{t.section_slug}/{t.slug}"
            for t in library.all_topics()
            if not t.title or not t.summary
        ]
        self.assertEqual(missing, [], "topics missing frontmatter")

    def test_slugs_have_no_numeric_prefix(self):
        """Ordering comes from the filename; the URL should not carry it."""
        for topic in library.all_topics():
            self.assertFalse(re.match(r"^\d", topic.slug), topic.slug)
            self.assertFalse(re.match(r"^\d", topic.section_slug), topic.section_slug)

    def test_reading_order_is_stable(self):
        topics = library.all_topics()
        first = topics[0]
        self.assertEqual(first.section_slug, "getting-started")
        self.assertEqual(first.slug, "what-dx-is")

    def test_every_topic_renders_to_html(self):
        for topic in library.all_topics():
            html, _toc = topic.render()
            self.assertTrue(html.strip(), f"{topic.path} rendered empty")

    def test_neighbours_walk_the_whole_library(self):
        topics = library.all_topics()
        previous, following = library.neighbours(topics[0])
        self.assertIsNone(previous)
        self.assertEqual(following, topics[1])

        previous, following = library.neighbours(topics[-1])
        self.assertIsNone(following)


class CrossLinkTests(TestCase):
    def test_no_broken_internal_links(self):
        known = {t.path for t in library.all_topics()}
        broken = []
        for topic in library.all_topics():
            for section, page in re.findall(
                r"\]\(/help/([a-z0-9-]+)/([a-z0-9-]+)/\)", topic.body
            ):
                if f"{section}/{page}" not in known:
                    broken.append(f"{topic.path} -> {section}/{page}")
        self.assertEqual(broken, [], "help topics link to pages that do not exist")

    def test_contextual_map_points_at_real_topics(self):
        from apps.help.views import CONTEXT_MAP

        known = {t.path for t in library.all_topics()}
        missing = sorted({v for v in CONTEXT_MAP.values() if v not in known})
        self.assertEqual(missing, [], "contextual help points at missing topics")

    def test_contextual_map_keys_are_real_views(self):
        from django.urls import NoReverseMatch, reverse as django_reverse

        from apps.help.views import CONTEXT_MAP

        unknown = []
        for view_name in CONTEXT_MAP:
            try:
                django_reverse(view_name)
            except NoReverseMatch:
                try:
                    django_reverse(view_name, args=["x"])
                except NoReverseMatch:
                    unknown.append(view_name)
        self.assertEqual(unknown, [], "contextual help keyed on views that do not exist")


class SearchTests(TestCase):
    def test_a_title_match_outranks_a_body_mention(self):
        hits = library.search("delta check")
        self.assertTrue(hits)
        self.assertEqual(hits[0].topic.slug, "delta-checks")

    def test_domain_terms_are_findable(self):
        for term, expected in [
            ("westgard", "westgard-rules"),
            ("haemolysis", None),
            ("loinc", "loinc"),
            ("read-back", None),
            ("installer", None),
        ]:
            with self.subTest(term=term):
                hits = library.search(term)
                self.assertTrue(hits, f"no help topic found for {term!r}")
                if expected:
                    self.assertEqual(hits[0].topic.slug, expected)

    def test_search_returns_an_excerpt(self):
        hits = library.search("levey-jennings")
        self.assertTrue(hits[0].excerpt.strip())

    def test_an_empty_query_returns_nothing(self):
        self.assertEqual(library.search("  "), [])


class HelpViewTests(TestCase):
    def setUp(self):
        self.user = make_user("help-reader", password=PASSWORD)
        self.client.force_login(self.user)

    def test_index_renders(self):
        response = self.client.get(reverse("help:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dx help library")

    def test_every_section_and_topic_renders(self):
        failures = []
        for section in library.load():
            if self.client.get(reverse("help:section", args=[section.slug])).status_code != 200:
                failures.append(section.slug)
            for topic in section.topics:
                response = self.client.get(
                    reverse("help:topic", args=[section.slug, topic.slug])
                )
                if response.status_code != 200:
                    failures.append(topic.path)
        self.assertEqual(failures, [])

    def test_a_topic_shows_its_content(self):
        response = self.client.get(
            reverse("help:topic", args=["quality", "westgard-rules"])
        )
        self.assertContains(response, "1-3s")
        self.assertContains(response, "systematic")

    def test_search_page_finds_a_topic(self):
        response = self.client.get(reverse("help:search"), {"q": "critical value"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Critical values")

    def test_unknown_topic_is_404(self):
        self.assertEqual(
            self.client.get(reverse("help:topic", args=["quality", "nope"])).status_code, 404
        )

    def test_contextual_help_redirects_to_the_right_topic(self):
        response = self.client.get(reverse("help:contextual"), {"for": "quality:qc"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("running-quality-control", response["Location"])

    def test_contextual_help_falls_back_to_the_index(self):
        response = self.client.get(reverse("help:contextual"), {"for": "nothing:known"})
        self.assertRedirects(response, reverse("help:index"))

    def test_help_requires_a_signed_in_user(self):
        self.client.logout()
        response = self.client.get(reverse("help:index"))
        self.assertEqual(response.status_code, 302)


class HelpAccessTests(TestCase):
    """Help contains documentation, not patient data — every role may read it."""

    def test_the_installer_may_read_the_whole_library(self):
        installer = make_installer("help-installer")
        self.client.force_login(installer)

        failures = []
        for section in library.load():
            for topic in section.topics:
                response = self.client.get(
                    reverse("help:topic", args=[section.slug, topic.slug])
                )
                if response.status_code != 200:
                    failures.append(topic.path)
        self.assertEqual(failures, [], "the installer was refused help pages")

    def test_help_appears_in_navigation_for_every_role(self):
        from apps.accounts.context_processors import navigation

        class FakeRequest:
            def __init__(self, user):
                self.user = user

        for role in ("installer", "admin", "manager", "scientist", "clerk"):
            with self.subTest(role=role):
                user = (
                    make_installer(f"nav-{role}")
                    if role == "installer"
                    else make_user(f"nav-{role}", role=role)
                )
                context = navigation(FakeRequest(user))
                names = {
                    item.url_name
                    for group in ("nav_workspace", "nav_oversight")
                    for item in context.get(group, [])
                }
                self.assertIn("help:index", names)

"""The `boxes` test helper also answers the window's own "What does this library hold?" box, so a wrong guess in a test is
seen at once instead of hanging the run (open item 6, 2026-11-21)."""

from tests.notes_gui_helpers import MEDIA_QUESTION, boxes  # noqa: F401 -- boxes is the fixture


def test_the_library_question_is_answered_cancel_and_kept(window, boxes):  # noqa: F811
    assert window._ask_media() == ""
    assert boxes.said(MEDIA_QUESTION)


def test_the_library_question_takes_the_answer_the_test_gives(window, boxes):  # noqa: F811
    boxes.media = "books"
    assert window._ask_media() == "books"

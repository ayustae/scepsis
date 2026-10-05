from chreos.body import sync_heading

BODY = "\n# Old title\n\nOld summary.\n\n## Description\n\nText with # Old title.\n"


def sync(body, old_title="Old title", new_title="Old title", old_summary="Old summary.", new_summary="Old summary."):
    return sync_heading(body, old_title, new_title, old_summary, new_summary)


def test_nothing_changed_is_a_noop():
    assert sync(BODY) == (BODY, [])


def test_title_is_replaced_when_h1_matches():
    body, warnings = sync(BODY, new_title="New title")
    assert body == BODY.replace("# Old title\n", "# New title\n", 1)
    assert warnings == []


def test_summary_is_replaced_when_paragraph_matches():
    body, warnings = sync(BODY, new_summary="New summary.")
    assert body == BODY.replace("Old summary.", "New summary.")
    assert warnings == []


def test_both_replaced():
    body, _ = sync(BODY, new_title="T", new_summary="S")
    assert body == "\n# T\n\nS\n\n## Description\n\nText with # Old title.\n"


def test_diverged_h1_is_left_untouched_with_warning():
    body = BODY.replace("# Old title", "# Hand edited")
    result, warnings = sync(body, new_title="New title")
    assert result == body
    assert len(warnings) == 1 and "H1" in warnings[0]


def test_diverged_summary_is_left_untouched_with_warning():
    body = BODY.replace("Old summary.", "Hand edited.")
    result, warnings = sync(body, new_summary="New summary.")
    assert result == body
    assert len(warnings) == 1 and "summary" in warnings[0]


def test_missing_h1_warns():
    body = "Just text.\n"
    result, warnings = sync(body, new_title="X", new_summary="Y")
    assert result == body
    assert len(warnings) == 2


def test_summary_added_when_there_was_none():
    body = "\n# Old title\n\n## Description\n\n"
    result, warnings = sync(body, old_summary=None, new_summary="Added.")
    assert result == "\n# Old title\n\nAdded.\n\n## Description\n\n"
    assert warnings == []


def test_summary_added_after_h1_at_end_of_body():
    result, _ = sync("\n# Old title\n\n", old_summary=None, new_summary="Added.")
    assert result == "\n# Old title\n\nAdded.\n\n"
    result, _ = sync("# Old title", old_summary=None, new_summary="Added.")
    assert result == "# Old title\n\nAdded.\n"


def test_summary_not_added_when_a_paragraph_already_exists():
    body = "\n# Old title\n\nSomeone wrote this.\n"
    result, warnings = sync(body, old_summary=None, new_summary="Added.")
    assert result == body
    assert len(warnings) == 1


def test_summary_removed_when_cleared():
    result, warnings = sync(BODY, new_summary=None)
    assert result == "\n# Old title\n\n## Description\n\nText with # Old title.\n"
    assert warnings == []


def test_summary_removed_at_end_of_body():
    result, _ = sync("\n# Old title\n\nOld summary.\n", new_summary=None)
    assert result == "\n# Old title\n"


def test_multiline_summary_paragraph_is_compared_as_a_whole():
    body = "# Old title\n\nline one\nline two\n\n## D\n"
    result, warnings = sync(body, old_summary="line one\nline two", new_summary="one line")
    assert result == "# Old title\n\none line\n\n## D\n"
    assert warnings == []


def test_heading_in_code_fence_is_ignored():
    body = "```\n# Old title\n```\n\n# Old title\n\nOld summary.\n"
    result, _ = sync(body, new_title="New")
    assert result == "```\n# Old title\n```\n\n# New\n\nOld summary.\n"


def test_crlf_is_preserved():
    body = "\r\n# Old title\r\n\r\nOld summary.\r\n"
    result, _ = sync(body, new_title="T", new_summary="S")
    assert result == "\r\n# T\r\n\r\nS\r\n"
    result, _ = sync("# Old title\r\n\r\n## D\r\n", old_summary=None, new_summary="S")
    assert result == "# Old title\r\n\r\nS\r\n\r\n## D\r\n"


def test_a_following_heading_is_not_a_summary():
    body = "# Old title\n\n## Old summary.\n"
    result, warnings = sync(body, new_summary="New")
    assert result == body
    assert len(warnings) == 1


def test_summary_added_when_h1_is_directly_followed_by_a_heading():
    result, _ = sync("# Old title\n## D\n", old_summary=None, new_summary="S")
    assert result == "# Old title\n\nS\n\n## D\n"

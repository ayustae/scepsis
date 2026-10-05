from chreos.markdown import has_unclosed_fence, newline_of, unfenced


def indices(text):
    return [index for index, _ in unfenced(text.splitlines(keepends=True))]


def test_plain_lines_are_all_unfenced():
    assert indices("a\nb\n") == [0, 1]


def test_backtick_fence_is_skipped_including_markers():
    assert indices("a\n```\n# x\n```\nb\n") == [0, 4]


def test_tilde_fence_with_info_string():
    assert indices("~~~python\n## x\n~~~\nb\n") == [3]


def test_closing_fence_must_use_the_same_character():
    assert indices("```\n~~~\n# x\n```\nb\n") == [4]


def test_closing_fence_must_be_at_least_as_long():
    assert indices("````\n```\n# x\n````\nb\n") == [4]


def test_closing_fence_cannot_have_an_info_string():
    assert indices("```\n```js\n```\nb\n") == [3]


def test_indented_fence_up_to_three_spaces():
    assert indices("   ```\nx\n   ```\nb\n") == [3]


def test_unclosed_fence_runs_to_the_end():
    lines = "a\n```\n# x\n".splitlines(keepends=True)
    assert [i for i, _ in unfenced(lines)] == [0]
    assert has_unclosed_fence(lines)
    assert not has_unclosed_fence("```\nx\n```\n".splitlines(keepends=True))


def test_newline_of():
    assert newline_of("a\r\nb") == "\r\n"
    assert newline_of("a\nb") == "\n"
    assert newline_of("") == "\n"

import re


def fn_to_re(pattern):
    re_pattern = []

    for sub_pattern in pattern.split('/'):
        if sub_pattern == '**':
            # Match anything, including slashes.
            re_pattern.append('.*')
        else:
            # Negative lookahead for anything except a forward slash.
            anything_but_slash = '[^\n/]*'
            re_pattern.append(re.escape(sub_pattern).replace('\\*', anything_but_slash))
    full_pattern = '/'.join(re_pattern)

    if pattern.startswith('/'):
        full_pattern = '^' + full_pattern
        full_pattern = full_pattern + '$'
    elif '/' not in pattern:
        # We have defined a pattern that must be the last element.
        full_pattern = '/' + full_pattern #+ '$'
    else:
        # If the pattern didn't start with a slash that means we want the pattern
        # to start at the beginning of a path level.
        # (e.g. "bc" should match "bc" but not "abc")
        full_pattern = '.*/' + full_pattern
    full_pattern = full_pattern + '$'
    return full_pattern

import six
class PathPattern:
    def __init__(self, fn_pattern):
        self._fn_pattern = fn_pattern
        self._compiled = re.compile(self._fn_pattern_to_re(self._fn_pattern))

    @staticmethod
    def _fn_pattern_to_re(fn_pattern):
        return fn_to_re(fn_pattern)

    def matches(self, path):
        assert path.startswith('/'), 'Untested with anything but absolute paths.'
        return bool(self._compiled.search(path))

    @staticmethod
    def create_from(thing):
        if isinstance(thing, (PathPattern, PathMultiPattern)):
            return thing
        elif isinstance(thing, six.string_types):
            return PathPattern(thing)
        elif isinstance(thing, list):
            return PathMultiPattern(*thing)
        else:
            raise ValueError(
                "Don't know how to make a PathPattern from a {}"
                "".format(type(thing).__name__))


class PathMultiPattern:
    def __init__(self, *patterns):
        self.patterns = [PathPattern(pattern) for pattern in patterns]

    def matches(self, path):
        for pattern in self.patterns:
            if pattern.matches(path):
                return True
        else:
            return False


def path_match(pattern, path):
    return 'match' if PathPattern(pattern).matches(path) else 'no match'


import pytest
@pytest.mark.parametrize('pattern, path, expected', [
    ['', '/a/b', 'no match'],   # Questionable. Possibly need to raise instead.
    ['a', '/a/b', 'no match'],
    ['/a', '/a', 'match'],
    ['/a', '/a/b', 'no match'],
    ['/b', '/a/b', 'no match'],
    ['*/b', '/a/b', 'match'],
    ['*/c', '/a/b/c', 'match'],
    ['/*/c', '/a/b/c', 'no match'],
    ['**/b', '/a/b', 'match'],
    ['*', '/a', 'match'],
    ['*', '/a/b', 'match'],
    ['/*', '/a/b', 'no match'],
    ['**', '/a/b', 'match'],
    ['/**', '/a/b', 'match'],
    ['/a/**/d', '/a/b/c/d', 'match'],
    ['/a/**/e', '/a/b/c/d', 'no match'],
    ['a/b', '/a/b', 'match'],
    ['/a/b', '/a/b', 'match'],
    ['/a/*', '/a/b', 'match'],
    ['/a/*', '/a/b/c', 'no match'],
    ['/a/**', '/a/b/c', 'match'],
    ['b/**', '/a/b/c', 'match'],
    ['/b/**', '/a/b/c', 'no match'],
    ['a', '/ab', 'no match'],
    ['b', '/ab', 'no match'],
    ['b/c', '/a/b/c', 'match'],
    ['b/c', '/ab/c', 'no match'],
    ['/b/c', '/ab/c', 'no match'],
    ['b/c/*', '/a/b/c/d', 'match'],
    ['b/**', '/a/b/c/d', 'match'],
    ['/b/c/*', '/a/b/c/d', 'no match'],
    ['b/c', '/a/b/c/d', 'no match'],
    ['b/c/', '/a/b/c/d', 'no match'],
    ['/b/c', '/a/b/c/d', 'no match'],

])
def test_path_match(pattern, path, expected):
    result = path_match(pattern, path)
    assert result == expected

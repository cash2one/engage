"""A simple dsl for building regular expressions.
"""
import re

class _regexp(object):
    """base class for regular expression components"""
    def __init__(self):
        pass

    def get_value(self):
        pass

    def compile(self):
        return re.compile(self.get_value())

    def match(self, s):
        return self.compile().match(s)

    def is_atomic(self):
        """If atomic, don't need paraens when using a unary operator"""
        return False

    def get_sub_value(self):
        if self.is_atomic():
            return self.get_value()
        else:
            return "(?:" + self.get_value() + ")"

    def must_start_line(self):
        return False

    def must_end_line(self):
        return False

    def __str__(self):
        return self.get_value()


def _must_be_re(subexp):
    """Helper to check that a subexpression passed in is an re, not
    a string
    """
    if type(subexp)==str or type(subexp)==unicode:
        raise Exception("Must wrap subexpression '%s' in a lit()" % subexp)
        
class lit(_regexp):
    """For string literals

    >>> print lit("abc").get_value()
    abc
    >>> print lit("xy z").get_value()
    xy\\ z
    """
    def __init__(self, val):
        if type(val)!=str and type(val)!=unicode:
            raise Exception("Literal must be a string")
        if len(val)==0:
            raise Exception("Cannot use empty string as a regexp literal")
        self.val = val

    def get_value(self):
        return re.escape(self.val)

    def is_atomic(self):
        return len(self.val)==1


class _unary_operator(_regexp):
    def __init__(self, subexp, op):
        super(_unary_operator, self).__init__()
        _must_be_re(subexp)
        self.subexp = subexp
        self.op = op

    def get_value(self):
        return "%s%s" % (self.subexp.get_sub_value(), self.op)

    def is_atomic(self):
        return False

    def must_start_line(self):
        return self.subexp.must_start_line()

    def must_end_line(self):
        return self.subexp.must_end_line()

    
class zero_or_one(_unary_operator):
    """
    >>> print zero_or_one(lit("a")).get_value()
    a?
    >>> print zero_or_one(lit("ab")).get_value()
    (?:ab)?
    """
    def __init__(self, subexp):
        super(zero_or_one, self).__init__(subexp, "?")

class one_or_more(_unary_operator):
    def __init__(self, subexp):
        super(one_or_more, self).__init__(subexp, "+")
        if self.subexp.must_start_line():
            raise Exception("Cannot have ^ inside a repeating expression: %s" % subexp)
        if self.subexp.must_end_line():
            raise Exception("Cannot have $ inside a repeating expression: %s" % subexp)


class zero_or_more(_unary_operator):
    def __init__(self, subexp):
        super(zero_or_more, self).__init__(subexp, "*")
        if self.subexp.must_start_line():
            raise Exception("Cannot have ^ inside a repeating expression: %s" % subexp)
        if self.subexp.must_end_line():
            raise Exception("Cannot have $ inside a repeating expression: %s" % subexp)


class _character_class(_regexp):
    def __init__(self, char_class):
        self.char_class = char_class

    def get_value(self):
        return self.char_class

    def is_atomic(self):
        return True
    
class any_except_newline(_character_class):
    """
    >>> print any_except_newline().get_value()
    .
    """
    def __init__(self):
        super(any_except_newline, self).__init__(".")


class whitespace_char(_character_class):
    """
    >>> print whitespace_char().get_value()
    \s
    >>> whitespace_char().compile().match(" ") is not None
    True
    >>> whitespace_char().compile().match("x") is not None
    False
    """
    def __init__(self):
        super(whitespace_char, self).__init__("\\s")


class character_set(_regexp):
    def __init__(self, chars):
        self.chars= chars

    def get_value(self):
        return "[%s]" % self.chars

    def is_atomic(self):
        return True

class complement_char_set(_regexp):
    def __init__(self, chars):
        self.chars= chars

    def get_value(self):
        return "[^%s]" % self.chars

    def is_atomic(self):
        return True
    
    
class or_match(_regexp):
    """
    >>> print or_match(lit("a"), lit("b")).get_value()
    a|b
    >>> print or_match(lit("a"), one_or_more(lit("b")), lit("c")).get_value()
    a|(?:b+)|c
    """
    def __init__(self, *args):
        self.subexp_list = args
        for subexp in self.subexp_list:
            _must_be_re(subexp)

    def get_value(self):
        return '|'.join([subexp.get_sub_value() for subexp in self.subexp_list])

    def is_atomic(self):
        return False

    def must_start_line(self):
        for subexp in self.subexp_list:
            if subexp.must_start_line():
                return True
        return False

    def must_end_line(self):
        for subexp in self.subexp_list:
            if subexp.must_end_line():
                return True
        return False

class group(_regexp):
    """
    >>> print group(lit('abc')).get_value()
    (abc)
    >>> print group(lit('abc'), name='test').get_value()
    (?P<test>abc)
    """
    def __init__(self, subexp, name=None):
        self.subexp = subexp
        _must_be_re(self.subexp)
        self.name = name

    def get_value(self):
        if self.name:
            return "(?P<%s>%s)" % (self.name, self.subexp.get_value())
        else:
            return "(" + self.subexp.get_value() + ")"

    def is_atomic(self):
        return True

    def must_start_line(self):
        return self.subexp.must_start_line()

    def must_end_line(self):
        return self.subexp.must_end_line()


class line_starts_with(_regexp):
    """
    >>> print line_starts_with(lit("x")).get_value()
    ^x
    """
    def __init__(self, subexp):
        _must_be_re(subexp)
        if subexp.must_start_line():
            raise Exception("Cannot use regexp pattern %s after ^" % subexp.get_value())
        self.subexp = subexp

    def get_value(self):
        return "^" + self.subexp.get_sub_value()

    def is_atomic(self):
        return False

    def must_start_line(self):
        return True


class line_ends_with(_regexp):
    """
    >>> print line_ends_with(lit("x")).get_value()
    x$
    """
    def __init__(self, subexp):
        _must_be_re(subexp)
        if subexp.must_end_line():
            raise Exception("Cannot use regexp pattern %s before $" % subexp.get_value())
        self.subexp = subexp

    def get_value(self):
        return self.subexp.get_sub_value() + "$"

    def is_atomic(self):
        return False

    def must_end_line(self):
        return True


class concat(_regexp):
    """Concatenate two or more regular expressions.

    >>> print concat(lit("a"), lit("b"), lit("c")).get_value()
    abc
    """
    def __init__(self, *args):
        self.subexp_list = args
        for subexp in self.subexp_list:
            _must_be_re(subexp)
        if len(self.subexp_list)<2:
            raise Exception("Concat subexpression list must have at least two items, got '%s'" %
                            self.subexp_list.__repr__())
        if self.subexp_list[0].must_end_line():
            raise Exception("Cannot use $ in pattern %s, which is not end of exp" % self.subexp_list[0].get_value())
        if self.subexp_list[-1].must_start_line():
            raise Exception("Cannot use ^ in pattern %s, which is not start of exp" % self.subexp_list[-1].get_value())
        for i in range(1, len(self.subexp_list)-1): # check all the middle members
            if self.subexp_list[i].must_end_line():
                raise Exception("Cannot use $ in pattern %s, which is not end of exp" % self.subexp_list[i].get_value())
            if self.subexp_list[i].must_start_line():
                raise Exception("Cannot use ^ in pattern %s, which is not start of exp" % self.subexp_list[i].get_value())

    def get_value(self):
        return "".join([e.get_value() for e in self.subexp_list])

    def is_atomic(self):
        return False

    def must_start_line(self):
        return self.subexp_list[0].must_start_line()

    def must_end_line(self):
        return self.subexp_list[1].must_end_line()


def match(p, s):
    """Helper function for debugging. Given regexp object p and
    a test string s, return the subset of s that matches p or
    None if there is no match.
    """
    mo = p.compile().match(s)
    if mo:
        return s[mo.start():mo.end()]
    else:
        return None


def search(p, s):
    """Helper function for debugging. Given regexp object p and
    a test string s, return the subset of s that is found via a search()
    None if there is no match.
    """
    mo = p.compile().search(s)
    if mo:
        return s[mo.start():mo.end()]
    else:
        return None



if __name__ == "__main__":
    import doctest
    doctest.testmod()

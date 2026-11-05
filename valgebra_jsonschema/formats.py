"""The ``format`` values read when a caller asks for them to assert.

Draft 2020-12 makes ``format`` an annotation by default, so this applies only on request. A
format with a regular language is a pattern, so a relation through it is decided; the rest are
predicates, exact on membership and opaque to a relation. Digits are ASCII throughout, since the
grammars these come from are written over ASCII.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable

_DAYS_31 = "(?:0[13578]|1[02])-(?:0[1-9]|[12][0-9]|3[01])"
_DAYS_30 = "(?:0[469]|11)-(?:0[1-9]|[12][0-9]|30)"
_DAYS_28 = "02-(?:0[1-9]|1[0-9]|2[0-8])"
_LEAP_YEAR = "(?:[0-9]{2}(?:0[48]|[2468][048]|[13579][26])|(?:[02468][048]|[13579][26])00)"
_DATE = f"(?:[0-9]{{4}}-(?:{_DAYS_31}|{_DAYS_30}|{_DAYS_28})|{_LEAP_YEAR}-02-29)"
_OCTET = "(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])"
_HEX4 = "[0-9a-fA-F]{4}"
_DUR_TIME = "T(?:[0-9]+H(?:[0-9]+M(?:[0-9]+S)?)?|[0-9]+M(?:[0-9]+S)?|[0-9]+S)"
_DUR_DATE = "(?:[0-9]+D|[0-9]+M(?:[0-9]+D)?|[0-9]+Y(?:[0-9]+M(?:[0-9]+D)?)?)"

#: The formats that are regular languages, by a pattern over the whole string.
LANGUAGES: dict[str, str] = {
    "date": _DATE,
    "duration": f"P(?:[0-9]+W|{_DUR_DATE}(?:{_DUR_TIME})?|{_DUR_TIME})",
    "ipv4": rf"{_OCTET}(?:\.{_OCTET}){{3}}",
    "uuid": f"{_HEX4}{_HEX4}-{_HEX4}-{_HEX4}-{_HEX4}-{_HEX4}{_HEX4}{_HEX4}",
}

_CLOCK = re.compile(
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})(?:\.[0-9]+)?(?:[zZ]|([+-])([0-9]{2}):([0-9]{2}))",
    re.ASCII,
)
_WHOLE_DATE = re.compile(_DATE, re.ASCII)
_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", re.ASCII)
_ATOM = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+", re.ASCII)
_QUOTED = re.compile(r'"(?:[^"\\\r\n]|\\[ -~])*"')
_DAY_MINUTES = 24 * 60
_MAX_HOSTNAME = 253
_MAX_HOUR = 23
_MAX_MINUTE = 59
_LEAP_SECOND = 60
_LAST_MINUTE = 23 * 60 + 59


def _is_time(text: str) -> bool:
    """Return whether ``text`` is RFC 3339's ``full-time``.

    A leap second is the last second of a UTC day, so where one is read depends on the offset.
    """
    match = _CLOCK.fullmatch(text)
    if match is None:
        return False
    hour, minute, second = int(match[1]), int(match[2]), int(match[3])
    if hour > _MAX_HOUR or minute > _MAX_MINUTE or second > _LEAP_SECOND:
        return False
    offset = 0
    if match[4]:
        off_hour, off_minute = int(match[5]), int(match[6])
        if off_hour > _MAX_HOUR or off_minute > _MAX_MINUTE:
            return False
        offset = (off_hour * 60 + off_minute) * (1 if match[4] == "+" else -1)
    if second < _LEAP_SECOND:
        return True
    return (hour * 60 + minute - offset) % _DAY_MINUTES == _LAST_MINUTE


def _is_date_time(text: str) -> bool:
    """Return whether ``text`` is RFC 3339's ``date-time``, whose separator may be lowercase."""
    date, separator, time = text[:10], text[10:11], text[11:]
    return separator in {"T", "t"} and _WHOLE_DATE.fullmatch(date) is not None and _is_time(time)


def _is_ipv6(text: str) -> bool:
    """Return whether ``text`` is an RFC 4291 address, which holds no zone."""
    if "%" in text:
        return False
    try:
        ipaddress.IPv6Address(text)
    except ValueError:
        return False
    return True


def _is_hostname(text: str) -> bool:
    """Return whether ``text`` is an RFC 1123 hostname.

    An ``xn--`` label is read as the label it spells: its Punycode and the IDNA rules on what it
    decodes to are not read, as `docs/03-conformance.md` records.
    """
    if not text or len(text) > _MAX_HOSTNAME:
        return False
    return all(_LABEL.fullmatch(label) for label in text.split("."))


def _is_domain_or_literal(domain: str) -> bool:
    """Return whether ``domain`` is a hostname, or an address literal in square brackets."""
    if domain.startswith("[") and domain.endswith("]"):
        literal = domain[1:-1]
        if literal[:5].lower() == "ipv6:":
            return _is_ipv6(literal[5:])
        try:
            ipaddress.IPv4Address(literal)
        except ValueError:
            return False
        return True
    return _is_hostname(domain)


def _is_email(text: str) -> bool:
    """Return whether ``text`` is an RFC 5321 ``Mailbox``: a local part, ``@``, and a domain."""
    local, at, domain = text.rpartition("@")
    if not at or not _is_domain_or_literal(domain):
        return False
    if local.startswith('"'):
        return _QUOTED.fullmatch(local) is not None
    return all(_ATOM.fullmatch(atom) for atom in local.split("."))


#: The formats held by a function: a predicate, exact on membership and opaque to a relation.
PREDICATES: dict[str, Callable[[str], bool]] = {
    "date-time": _is_date_time,
    "email": _is_email,
    "hostname": _is_hostname,
    "ipv6": _is_ipv6,
    "time": _is_time,
}
